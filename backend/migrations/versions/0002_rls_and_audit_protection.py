"""Row Level Security for tenant tables and insert-only audit events.

RLS is a second line of defence behind application authorisation (multi-tenancy.md).
Policies compare organisation_id to the transaction-local setting app.current_org,
which the API sets only after verifying membership. With no setting, no rows match.
FORCE ROW LEVEL SECURITY applies the policies to the table owner as well.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "customers",
    "stored_files",
    "import_batches",
    "import_rows",
    "invoices",
    "invoice_versions",
    "credit_notes",
    "payments",
    "allocations",
)

_CURRENT_ORG = "NULLIF(current_setting('app.current_org', true), '')::uuid"


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (organisation_id = {_CURRENT_ORG}) "
            f"WITH CHECK (organisation_id = {_CURRENT_ORG})"
        )

    # Audit events: tenant events are readable only within their organisation. Identity events
    # (NULL organisation, e.g. logins) are readable only outside any tenant context, never by a tenant.
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY audit_read ON audit_events FOR SELECT "
        f"USING (organisation_id = {_CURRENT_ORG} OR (organisation_id IS NULL AND {_CURRENT_ORG} IS NULL))"
    )
    op.execute(
        "CREATE POLICY audit_insert ON audit_events FOR INSERT "
        f"WITH CHECK (organisation_id IS NULL OR organisation_id = {_CURRENT_ORG})"
    )

    op.execute(
        """
        CREATE FUNCTION vx_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is insert-only';
        END;
        $$;
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION vx_audit_immutable()"
    )

    # Allocations may only change status confirmed -> reversed; amounts and links are immutable.
    op.execute(
        """
        CREATE FUNCTION vx_allocation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'allocations cannot be deleted; reverse them instead';
            END IF;
            IF NEW.amount <> OLD.amount OR NEW.invoice_id <> OLD.invoice_id
               OR NEW.payment_id IS DISTINCT FROM OLD.payment_id
               OR NEW.credit_note_id IS DISTINCT FROM OLD.credit_note_id
               OR NEW.effective_date <> OLD.effective_date
               OR NEW.organisation_id <> OLD.organisation_id THEN
                RAISE EXCEPTION 'allocation values are immutable';
            END IF;
            IF OLD.status = 'reversed' THEN
                RAISE EXCEPTION 'a reversed allocation cannot change';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        "CREATE TRIGGER allocations_guard BEFORE UPDATE OR DELETE ON allocations "
        "FOR EACH ROW EXECUTE FUNCTION vx_allocation_guard()"
    )

    # Invoice versions and committed source rows are immutable history.
    op.execute(
        """
        CREATE FUNCTION vx_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is immutable', TG_TABLE_NAME;
        END;
        $$;
        """
    )
    op.execute(
        "CREATE TRIGGER invoice_versions_immutable BEFORE UPDATE OR DELETE ON invoice_versions "
        "FOR EACH ROW EXECUTE FUNCTION vx_immutable()"
    )
    op.execute(
        """
        CREATE FUNCTION vx_import_row_raw_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.raw IS DISTINCT FROM OLD.raw THEN
                RAISE EXCEPTION 'raw imported values are immutable';
            END IF;
            IF TG_OP = 'DELETE' AND OLD.status IN ('committed','amendment_pending','amendment_approved',
                                                    'amendment_rejected','duplicate_skipped') THEN
                RAISE EXCEPTION 'committed import rows cannot be deleted';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        "CREATE TRIGGER import_rows_raw_guard BEFORE UPDATE OR DELETE ON import_rows "
        "FOR EACH ROW EXECUTE FUNCTION vx_import_row_raw_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS import_rows_raw_guard ON import_rows")
    op.execute("DROP FUNCTION IF EXISTS vx_import_row_raw_guard()")
    op.execute("DROP TRIGGER IF EXISTS invoice_versions_immutable ON invoice_versions")
    op.execute("DROP FUNCTION IF EXISTS vx_immutable()")
    op.execute("DROP TRIGGER IF EXISTS allocations_guard ON allocations")
    op.execute("DROP FUNCTION IF EXISTS vx_allocation_guard()")
    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS vx_audit_immutable()")
    op.execute("DROP POLICY IF EXISTS audit_insert ON audit_events")
    op.execute("DROP POLICY IF EXISTS audit_read ON audit_events")
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
