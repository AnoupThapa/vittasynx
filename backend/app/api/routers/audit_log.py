from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import OrgContext, require
from app.core.permissions import Perm
from app.models import AuditEvent, User

router = APIRouter(prefix="/orgs/{org_id}/audit", tags=["audit"])


@router.get("")
def audit_events(limit: int = 100, offset: int = 0, entity_type: str | None = None,
                 ctx: OrgContext = Depends(require(Perm.VIEW_AUDIT))) -> dict:
    q = select(AuditEvent).where(AuditEvent.organisation_id == ctx.org_id)
    if entity_type:
        q = q.where(AuditEvent.entity_type == entity_type)
    events = list(ctx.db.scalars(q.order_by(AuditEvent.created_at.desc()).limit(max(1, min(limit, 500))).offset(max(0, offset))))
    names = {u.id: u.full_name for u in ctx.db.scalars(select(User).where(User.id.in_({e.actor_user_id for e in events if e.actor_user_id})))}
    return {"items": [{"id": str(e.id), "action": e.action, "entity_type": e.entity_type,
                       "entity_id": str(e.entity_id) if e.entity_id else None, "actor": names.get(e.actor_user_id),
                       "at": e.created_at.isoformat(), "before": e.before, "after": e.after, "source": e.source,
                       "note": e.note} for e in events]}
