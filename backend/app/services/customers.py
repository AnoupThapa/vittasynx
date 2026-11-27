from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domain.normalise import normalise_name
from app.models import Customer
from app.services import audit


def _clean_code(code: str | None) -> str | None:
    if code is None:
        return None
    code = code.strip()
    return code or None


def get(db: Session, org_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    c = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.organisation_id == org_id))
    if c is None:
        raise NotFound("Customer not found")
    return c


def find_by_code(db: Session, org_id: uuid.UUID, code: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.organisation_id == org_id, Customer.code == code.strip()))


def find_by_name(db: Session, org_id: uuid.UUID, name: str) -> list[Customer]:
    return list(db.scalars(select(Customer).where(Customer.organisation_id == org_id,
                                                  Customer.normalised_name == normalise_name(name))))


def create(db: Session, org_id: uuid.UUID, actor_id: uuid.UUID, name: str, code: str | None, source: str = "api") -> Customer:
    if not name or not name.strip():
        raise ValidationFailed("Customer name is required")
    code = _clean_code(code)
    if code and find_by_code(db, org_id, code):
        raise Conflict(f"A customer with code {code} already exists", code="customer_code_taken")
    if not code and find_by_name(db, org_id, name):
        raise Conflict("A customer with this name already exists; add a customer code to distinguish them",
                       code="customer_name_taken")
    c = Customer(organisation_id=org_id, code=code, name=name.strip(), normalised_name=normalise_name(name),
                 created_by=actor_id)
    db.add(c)
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflict("Customer already exists", code="customer_exists") from exc
    audit.record(db, action="customer.created", actor_user_id=actor_id, organisation_id=org_id,
                 entity_type="customer", entity_id=c.id, after={"name": c.name, "code": c.code}, source=source)
    return c


def update(db: Session, org_id: uuid.UUID, actor_id: uuid.UUID, customer: Customer, *, name=None, code=None,
           status=None, code_set: bool = False) -> Customer:
    before = {"name": customer.name, "code": customer.code, "status": customer.status}
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Customer name is required")
        customer.name = name.strip()
        customer.normalised_name = normalise_name(name)
    if code_set:
        new_code = _clean_code(code)
        if new_code and new_code != customer.code:
            other = find_by_code(db, org_id, new_code)
            if other and other.id != customer.id:
                raise Conflict(f"A customer with code {new_code} already exists", code="customer_code_taken")
        customer.code = new_code
    if status is not None:
        if status not in ("active", "inactive"):
            raise ValidationFailed("Status must be active or inactive")
        customer.status = status
    customer.updated_at = datetime.now(timezone.utc)
    audit.record(db, action="customer.updated", actor_user_id=actor_id, organisation_id=org_id,
                 entity_type="customer", entity_id=customer.id, before=before,
                 after={"name": customer.name, "code": customer.code, "status": customer.status})
    return customer


def search(db: Session, org_id: uuid.UUID, q: str | None, status: str | None) -> list[Customer]:
    stmt = select(Customer).where(Customer.organisation_id == org_id)
    if q:
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(or_(Customer.normalised_name.like(f"%{term.casefold()}%", escape="\\"),
                              Customer.code.ilike(f"%{term}%", escape="\\")))
    if status:
        stmt = stmt.where(Customer.status == status)
    return list(db.scalars(stmt.order_by(Customer.name)))
