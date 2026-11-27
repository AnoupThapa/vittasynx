"""Role-based permissions (approved decision D-03). Enforced by the API layer only — never the UI."""
from enum import Enum


class Perm(str, Enum):
    VIEW = "view"
    EXPORT = "export"
    MANAGE_CUSTOMERS = "manage_customers"
    IMPORT = "import"
    APPROVE_AMENDMENT = "approve_amendment"
    RECORD_PAYMENT = "record_payment"
    CONFIRM_ALLOCATION = "confirm_allocation"
    REVERSE_ALLOCATION = "reverse_allocation"
    MANAGE_CREDITS_AND_STATUS = "manage_credits_and_status"
    VIEW_AUDIT = "view_audit"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_SETTINGS = "manage_settings"
    OWNER_ACTIONS = "owner_actions"


_ALL = set(Perm)
_FINANCE = _ALL - {Perm.MANAGE_MEMBERS, Perm.MANAGE_SETTINGS, Perm.OWNER_ACTIONS}
_AR = {
    Perm.VIEW,
    Perm.EXPORT,
    Perm.MANAGE_CUSTOMERS,
    Perm.IMPORT,
    Perm.RECORD_PAYMENT,
    Perm.CONFIRM_ALLOCATION,
}

ROLE_PERMISSIONS: dict[str, frozenset[Perm]] = {
    "owner": frozenset(_ALL),
    "admin": frozenset(_ALL - {Perm.OWNER_ACTIONS}),
    "finance_manager": frozenset(_FINANCE),
    "ar_officer": frozenset(_AR),
    "read_only": frozenset({Perm.VIEW}),
}

PRIVILEGED_ROLES = frozenset({"owner", "admin"})

ROLE_LABELS = {
    "owner": "Organisation Owner",
    "admin": "Administrator",
    "finance_manager": "Finance Manager",
    "ar_officer": "Accounts Receivable Officer",
    "read_only": "Read-only User",
}


def has_permission(role: str, perm: Perm) -> bool:
    return perm in ROLE_PERMISSIONS.get(role, frozenset())
