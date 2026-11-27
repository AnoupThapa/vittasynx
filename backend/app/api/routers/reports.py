from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.common import reporting_date
from app.api.deps import OrgContext, require
from app.core.permissions import Perm
from app.services import audit, reporting

router = APIRouter(prefix="/orgs/{org_id}", tags=["reports"])


@router.get("/dashboard")
def dashboard(as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    return reporting.dashboard(ctx.db, ctx.org, reporting_date(ctx, as_at))


@router.get("/reports/customer-balances")
def customer_balances(as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    r = reporting_date(ctx, as_at)
    return {"reporting_date": r.isoformat(), "currency": ctx.org.currency,
            "items": reporting.customer_balances(ctx.db, ctx.org, r)}


def _csv(ctx: OrgContext, name: str, content: str, as_at: date) -> Response:
    audit.record(ctx.db, action="report.exported", actor_user_id=ctx.user.id, organisation_id=ctx.org_id,
                 entity_type="report", after={"report": name, "reporting_date": as_at.isoformat()})
    ctx.db.commit()
    return Response(content=content, media_type="text/csv; charset=utf-8",
                    headers={"content-disposition": f'attachment; filename="{name}-{as_at.isoformat()}.csv"'})


_INVOICE_COLS = [("invoice_number", "Invoice number"), ("customer_name", "Customer"), ("issue_date", "Issue date"),
                 ("due_date", "Due date"), ("original_amount", "Original amount"),
                 ("payments_allocated", "Payments allocated"), ("credits_allocated", "Credits allocated"),
                 ("balance", "Balance"), ("status", "Status"), ("days_past_due", "Days past due"),
                 ("ageing_bucket", "Ageing bucket"), ("source_amount_due", "Source-reported amount due")]


@router.get("/exports/invoices.csv")
def export_invoices(as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.EXPORT))) -> Response:
    r = reporting_date(ctx, as_at)
    rows = reporting.invoice_rows(ctx.db, ctx.org, r)
    return _csv(ctx, "invoice-register", reporting.to_csv(rows, _INVOICE_COLS,
                                                           reporting.preamble(ctx.org, "Invoice register", r)), r)


@router.get("/exports/ageing.csv")
def export_ageing(as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.EXPORT))) -> Response:
    r = reporting_date(ctx, as_at)
    rows = [x for x in reporting.customer_balances(ctx.db, ctx.org, r) if x["total_outstanding"] != "0.00"]
    cols = [("customer_code", "Customer code"), ("customer_name", "Customer"), ("current", "Current"),
            ("1_30", "1-30 days"), ("31_60", "31-60 days"), ("61_90", "61-90 days"), ("91_plus", "91+ days"),
            ("total_outstanding", "Total outstanding")]
    return _csv(ctx, "ageing", reporting.to_csv(rows, cols, reporting.preamble(ctx.org, "Receivables ageing", r)), r)


@router.get("/exports/customer-balances.csv")
def export_customer_balances(as_at: date | None = None, ctx: OrgContext = Depends(require(Perm.EXPORT))) -> Response:
    r = reporting_date(ctx, as_at)
    rows = reporting.customer_balances(ctx.db, ctx.org, r)
    cols = [("customer_code", "Customer code"), ("customer_name", "Customer"), ("status", "Status"),
            ("total_outstanding", "Total outstanding"), ("overdue", "Overdue"),
            ("unapplied_payments", "Unapplied payments"), ("unapplied_credits", "Unapplied credits")]
    return _csv(ctx, "customer-balances", reporting.to_csv(rows, cols,
                                                            reporting.preamble(ctx.org, "Customer balances", r)), r)
