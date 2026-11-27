import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import OrgContext, current_user, require
from app.core.permissions import ROLE_LABELS, Perm
from app.db import get_db
from app.models import Membership, Organisation, User
from app.config import get_settings
from app.services import organisations as svc
from app.services.ratelimit import client_ip, hit

router = APIRouter(tags=["organisations"])


class OrgIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=1, max_length=64)


class OrgPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)


class RoleIn(BaseModel):
    role: str


class InviteIn(BaseModel):
    email: EmailStr
    role: str


class AcceptIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class TransferIn(BaseModel):
    user_id: uuid.UUID


def org_out(org: Organisation, role: str | None = None) -> dict:
    out = {"id": str(org.id), "name": org.name, "currency": org.currency, "timezone": org.timezone,
           "created_at": org.created_at.isoformat()}
    if role:
        out["role"] = role
        out["role_label"] = ROLE_LABELS[role]
    return out


def member_out(m: Membership) -> dict:
    return {"user_id": str(m.user_id), "email": m.user.email, "full_name": m.user.full_name, "role": m.role,
            "role_label": ROLE_LABELS[m.role], "mfa_enabled": m.user.mfa_enabled, "joined_at": m.created_at.isoformat()}


@router.post("/orgs", status_code=201)
def create_org(body: OrgIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    org = svc.create_organisation(db, user, body.name, body.currency, body.timezone)
    db.commit()
    return org_out(org, "owner")


@router.get("/orgs")
def list_orgs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"items": [org_out(m.organisation, m.role) for m in svc.memberships_for(db, user)]}


@router.get("/orgs/{org_id}")
def get_org(ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    return org_out(ctx.org, ctx.role)


@router.patch("/orgs/{org_id}")
def update_org(body: OrgPatch, ctx: OrgContext = Depends(require(Perm.MANAGE_SETTINGS))) -> dict:
    svc.update_organisation(ctx.db, ctx.user, ctx.org, body.name, body.timezone)
    ctx.db.commit()
    return org_out(ctx.org, ctx.role)


@router.get("/orgs/{org_id}/members")
def members(ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    return {"items": [member_out(m) for m in svc.list_members(ctx.db, ctx.org)]}


@router.patch("/orgs/{org_id}/members/{user_id}")
def change_role(user_id: uuid.UUID, body: RoleIn, ctx: OrgContext = Depends(require(Perm.MANAGE_MEMBERS))) -> dict:
    m = svc.change_role(ctx.db, ctx.membership, ctx.org, user_id, body.role)
    ctx.db.commit()
    return member_out(m)


@router.delete("/orgs/{org_id}/members/{user_id}")
def remove_member(user_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.MANAGE_MEMBERS))) -> dict:
    svc.remove_member(ctx.db, ctx.membership, ctx.org, user_id)
    ctx.db.commit()
    return {"ok": True}


@router.post("/orgs/{org_id}/transfer-ownership")
def transfer(body: TransferIn, ctx: OrgContext = Depends(require(Perm.OWNER_ACTIONS))) -> dict:
    svc.transfer_ownership(ctx.db, ctx.membership, ctx.org, body.user_id)
    ctx.db.commit()
    return {"ok": True}


@router.get("/orgs/{org_id}/invitations")
def invitations(ctx: OrgContext = Depends(require(Perm.MANAGE_MEMBERS))) -> dict:
    return {"items": [{"id": str(i.id), "email": i.email, "role": i.role, "expires_at": i.expires_at.isoformat()}
                      for i in svc.list_invitations(ctx.db, ctx.org)]}


@router.post("/orgs/{org_id}/invitations", status_code=201)
def invite(body: InviteIn, ctx: OrgContext = Depends(require(Perm.MANAGE_MEMBERS))) -> dict:
    inv = svc.invite(ctx.db, ctx.user, ctx.org, body.email, body.role)
    ctx.db.commit()
    return {"id": str(inv.id), "email": inv.email, "role": inv.role, "expires_at": inv.expires_at.isoformat()}


@router.delete("/orgs/{org_id}/invitations/{invitation_id}")
def revoke(invitation_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.MANAGE_MEMBERS))) -> dict:
    svc.revoke_invitation(ctx.db, ctx.user, ctx.org, invitation_id)
    ctx.db.commit()
    return {"ok": True}


@router.post("/invitations/accept")
def accept(body: AcceptIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    hit(db, f"accept:ip:{client_ip(request)}", get_settings().accept_invite_limit_per_ip, 3600)
    m = svc.accept_invitation(db, user, body.token)
    db.commit()
    return org_out(m.organisation, m.role)
