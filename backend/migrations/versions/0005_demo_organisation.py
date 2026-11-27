"""demo organisation

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-27 14:25:34.219583
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organisations', sa.Column('is_demo', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('organisations', sa.Column('demo_owner_id', sa.UUID(), nullable=True))
    op.create_unique_constraint('uq_organisations_demo_owner', 'organisations', ['demo_owner_id'])
    op.create_foreign_key('fk_organisations_demo_owner', 'organisations', 'users', ['demo_owner_id'], ['id'])
    op.drop_constraint('ck_invoices_entry_method', 'invoices', type_='check')
    op.create_check_constraint('ck_invoices_entry_method', 'invoices', "entry_method IN ('import','manual','demo')")


def downgrade() -> None:
    # Never silently delete or rewrite financial records: refuse while demo invoices exist.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM organisations WHERE is_demo) THEN
                RAISE EXCEPTION 'Demo organisations exist; remove them deliberately before downgrading 0005';
            END IF;
        END $$;
    """)
    op.drop_constraint('ck_invoices_entry_method', 'invoices', type_='check')
    op.create_check_constraint('ck_invoices_entry_method', 'invoices', "entry_method IN ('import','manual')")
    op.drop_constraint('fk_organisations_demo_owner', 'organisations', type_='foreignkey')
    op.drop_constraint('uq_organisations_demo_owner', 'organisations', type_='unique')
    op.drop_column('organisations', 'demo_owner_id')
    op.drop_column('organisations', 'is_demo')
