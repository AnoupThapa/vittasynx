from datetime import date

from app.api.deps import OrgContext
from app.services.receivables import org_today


def reporting_date(ctx: OrgContext, as_at: date | None) -> date:
    """Explicit reporting date; defaults to today in the organisation's timezone (D-16)."""
    return as_at or org_today(ctx.org)
