import pytest

from tests.conftest import token_from_email


def test_create_org_creator_is_owner(make_user, make_org):
    owner = make_user()
    org = make_org(owner)
    me = owner.get("/api/v1/auth/me").json()
    assert me["organisations"][0]["id"] == org and me["organisations"][0]["role"] == "owner"


@pytest.mark.parametrize("body,code", [
    ({"name": "X", "currency": "XYZ", "timezone": "Australia/Sydney"}, "unsupported_currency"),
    ({"name": "X", "currency": "AUD", "timezone": "Mars/Base"}, "invalid_timezone"),
])
def test_create_org_validation(make_user, body, code):
    assert make_user().post("/api/v1/orgs", json=body).json()["error"]["code"] == code


def test_update_org_settings(make_user, make_org):
    owner = make_user()
    org = make_org(owner)
    r = owner.patch(f"/api/v1/orgs/{org}", json={"name": "Renamed", "timezone": "Asia/Kathmandu"})
    assert r.json()["name"] == "Renamed" and r.json()["timezone"] == "Asia/Kathmandu"


def test_invitation_flow(make_user, make_org, make_client):
    owner = make_user()
    org = make_org(owner)
    invitee = make_user(email="new@example.com")
    r = owner.post(f"/api/v1/orgs/{org}/invitations", json={"email": "new@example.com", "role": "finance_manager"})
    assert r.status_code == 201
    token = token_from_email("new@example.com")
    assert invitee.get(f"/api/v1/orgs/{org}").status_code == 404  # not yet a member
    r = invitee.post("/api/v1/invitations/accept", json={"token": token})
    assert r.status_code == 200 and r.json()["role"] == "finance_manager"
    assert invitee.get(f"/api/v1/orgs/{org}").status_code == 200
    assert invitee.post("/api/v1/invitations/accept", json={"token": token}).status_code == 422  # single use


def test_invitation_requires_matching_verified_email(make_user, make_org):
    owner = make_user()
    org = make_org(owner)
    owner.post(f"/api/v1/orgs/{org}/invitations", json={"email": "target@example.com", "role": "read_only"})
    token = token_from_email("target@example.com")
    attacker = make_user(email="attacker@example.com")
    r = attacker.post("/api/v1/invitations/accept", json={"token": token})
    assert r.status_code == 403 and r.json()["error"]["code"] == "invitation_email_mismatch"
    unverified = make_user(email="target@example.com", verified=False)
    r = unverified.post("/api/v1/invitations/accept", json={"token": token})
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"


def test_owner_cannot_be_invited_as_owner(make_user, make_org):
    owner = make_user()
    org = make_org(owner)
    r = owner.post(f"/api/v1/orgs/{org}/invitations", json={"email": "x@example.com", "role": "owner"})
    assert r.status_code == 422


def test_revoked_invitation_cannot_be_used(make_user, make_org):
    owner = make_user()
    org = make_org(owner)
    invitee = make_user(email="rev@example.com")
    inv = owner.post(f"/api/v1/orgs/{org}/invitations", json={"email": "rev@example.com", "role": "read_only"}).json()
    token = token_from_email("rev@example.com")
    assert owner.delete(f"/api/v1/orgs/{org}/invitations/{inv['id']}").status_code == 200
    assert invitee.post("/api/v1/invitations/accept", json={"token": token}).status_code == 422


def test_role_change_and_owner_protection(make_user, make_org, add_member):
    owner = make_user()
    org = make_org(owner)
    admin = add_member(owner, org, "admin")
    ar = add_member(owner, org, "ar_officer")
    assert admin.patch(f"/api/v1/orgs/{org}/members/{ar.user_id}", json={"role": "finance_manager"}).json()["role"] == "finance_manager"
    r = admin.patch(f"/api/v1/orgs/{org}/members/{owner.user_id}", json={"role": "read_only"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "owner_protected"
    assert admin.delete(f"/api/v1/orgs/{org}/members/{owner.user_id}").status_code == 403
    assert admin.patch(f"/api/v1/orgs/{org}/members/{ar.user_id}", json={"role": "owner"}).status_code == 422
    assert admin.patch(f"/api/v1/orgs/{org}/members/{admin.user_id}", json={"role": "finance_manager"}).status_code == 403


def test_removed_member_loses_access(make_user, make_org, add_member):
    owner = make_user()
    org = make_org(owner)
    fm = add_member(owner, org, "finance_manager")
    assert fm.get(f"/api/v1/orgs/{org}/dashboard").status_code == 200
    assert owner.delete(f"/api/v1/orgs/{org}/members/{fm.user_id}").status_code == 200
    assert fm.get(f"/api/v1/orgs/{org}/dashboard").status_code == 404
    assert fm.get(f"/api/v1/orgs/{org}/customers").status_code == 404


def test_transfer_ownership(make_user, make_org, add_member):
    owner = make_user()
    org = make_org(owner)
    admin = add_member(owner, org, "admin")
    assert admin.post(f"/api/v1/orgs/{org}/transfer-ownership", json={"user_id": admin.user_id}).status_code == 403
    assert owner.post(f"/api/v1/orgs/{org}/transfer-ownership", json={"user_id": admin.user_id}).status_code == 200
    roles = {m["user_id"]: m["role"] for m in owner.get(f"/api/v1/orgs/{org}/members").json()["items"]}
    assert roles == {owner.user_id: "admin", admin.user_id: "owner"}


def test_user_in_multiple_orgs_switches_by_url(make_user, make_org, add_member):
    a_owner, b_owner = make_user(), make_user()
    org_a, org_b = make_org(a_owner, "A Pty Ltd"), make_org(b_owner, "B Pty Ltd")
    advisor = add_member(a_owner, org_a, "read_only")
    b_owner.post(f"/api/v1/orgs/{org_b}/invitations", json={"email": advisor.email, "role": "finance_manager"})
    advisor.post("/api/v1/invitations/accept", json={"token": token_from_email(advisor.email)})
    orgs = {o["id"]: o["role"] for o in advisor.get("/api/v1/auth/me").json()["organisations"]}
    assert orgs == {org_a: "read_only", org_b: "finance_manager"}
    # Role is evaluated per organisation.
    assert advisor.post(f"/api/v1/orgs/{org_a}/customers", json={"name": "Nope"}).status_code == 403
    assert advisor.post(f"/api/v1/orgs/{org_b}/customers", json={"name": "Yes"}).status_code == 201


def test_membership_changes_are_audited(make_user, make_org, add_member):
    owner = make_user()
    org = make_org(owner)
    ar = add_member(owner, org, "ar_officer")
    owner.patch(f"/api/v1/orgs/{org}/members/{ar.user_id}", json={"role": "read_only"})
    actions = [e["action"] for e in owner.get(f"/api/v1/orgs/{org}/audit").json()["items"]]
    for a in ("organisation.created", "invitation.created", "invitation.accepted", "membership.role_changed"):
        assert a in actions
