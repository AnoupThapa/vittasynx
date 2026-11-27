import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import OrgContext, require
from app.config import get_settings
from app.core.errors import ValidationFailed
from app.core.permissions import Perm
from app.models import ImportBatch, ImportRow, StoredFile
from app.services.imports import service as svc
from app.services.imports.fields import FIELDS

router = APIRouter(prefix="/orgs/{org_id}", tags=["imports"])


class MappingIn(BaseModel):
    mapping: dict[str, str]
    date_format: str = "DD/MM/YYYY"
    status_map: dict[str, str] | None = None


class RowAction(BaseModel):
    action: str
    corrections: dict[str, str] | None = None


class CommitIn(BaseModel):
    confirm_new_customers: bool = False
    exclude_errors: bool = False


class ReviewIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


def batch_out(db, b: ImportBatch, *, include_preview: bool = False) -> dict:
    f = db.get(StoredFile, b.file_id)
    out = {
        "id": str(b.id), "kind": b.kind, "status": b.status, "filename": f.original_filename if f else None,
        "headers": b.headers, "mapping": b.mapping, "options": b.options, "summary": b.summary,
        "warnings": b.warnings, "created_at": b.created_at.isoformat(),
        "committed_at": b.committed_at.isoformat() if b.committed_at else None,
        "fields": [{"key": fd.key, "label": fd.label, "required": fd.required} for fd in FIELDS[b.kind]],
    }
    if include_preview:
        out["preview"] = [{"row_number": r.row_number, "values": r.raw} for r in svc.rows(db, b, limit=svc.PREVIEW_ROWS)]
    return out


def row_out(r: ImportRow) -> dict:
    return {"id": str(r.id), "row_number": r.row_number, "status": r.status, "raw": r.raw,
            "corrections": r.corrections, "normalised": r.normalised, "messages": r.messages,
            "target_type": r.target_type, "target_id": str(r.target_id) if r.target_id else None}


@router.get("/import-fields")
def import_fields(ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    return {k: [{"key": f.key, "label": f.label, "required": f.required} for f in v] for k, v in FIELDS.items()}


@router.post("/imports", status_code=201)
async def upload(kind: str = Form(...), file: UploadFile = File(...),
                 ctx: OrgContext = Depends(require(Perm.IMPORT))) -> dict:
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailed(f"The file is larger than {limit // (1024 * 1024)} MB", code="file_too_large")
    batch = svc.upload(ctx.db, ctx.org, ctx.user.id, kind, file.filename or "upload", data)
    ctx.db.commit()
    return batch_out(ctx.db, batch, include_preview=True)


@router.get("/imports")
def list_imports(ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    from sqlalchemy import select

    batches = ctx.db.scalars(select(ImportBatch).where(ImportBatch.organisation_id == ctx.org_id)
                             .order_by(ImportBatch.created_at.desc()).limit(100))
    return {"items": [batch_out(ctx.db, b) for b in batches]}


@router.get("/imports/{batch_id}")
def get_import(batch_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    return batch_out(ctx.db, svc.get_batch(ctx.db, ctx.org_id, batch_id), include_preview=True)


@router.post("/imports/{batch_id}/validate")
def validate(batch_id: uuid.UUID, body: MappingIn, ctx: OrgContext = Depends(require(Perm.IMPORT))) -> dict:
    b = svc.configure_and_validate(ctx.db, ctx.org, ctx.user.id, batch_id, body.mapping, body.date_format, body.status_map)
    ctx.db.commit()
    return batch_out(ctx.db, b)


@router.get("/imports/{batch_id}/rows")
def import_rows(batch_id: uuid.UUID, status: str | None = None, limit: int = 200, offset: int = 0,
                ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    b = svc.get_batch(ctx.db, ctx.org_id, batch_id)
    limit = max(1, min(limit, 1000))
    return {"items": [row_out(r) for r in svc.rows(ctx.db, b, status, limit, max(0, offset))]}


@router.patch("/imports/{batch_id}/rows/{row_id}")
def update_row(batch_id: uuid.UUID, row_id: uuid.UUID, body: RowAction,
               ctx: OrgContext = Depends(require(Perm.IMPORT))) -> dict:
    b = svc.update_row(ctx.db, ctx.org, ctx.user.id, batch_id, row_id, body.action, body.corrections)
    ctx.db.commit()
    return batch_out(ctx.db, b)


@router.post("/imports/{batch_id}/commit")
def commit(batch_id: uuid.UUID, body: CommitIn, ctx: OrgContext = Depends(require(Perm.IMPORT))) -> dict:
    b = svc.commit(ctx.db, ctx.org, ctx.user.id, batch_id, confirm_new_customers=body.confirm_new_customers,
                   exclude_errors=body.exclude_errors)
    ctx.db.commit()
    return batch_out(ctx.db, b)


@router.post("/imports/{batch_id}/cancel")
def cancel(batch_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.IMPORT))) -> dict:
    b = svc.cancel(ctx.db, ctx.org, ctx.user.id, batch_id)
    ctx.db.commit()
    return batch_out(ctx.db, b)


@router.get("/imports/{batch_id}/file")
def download_source(batch_id: uuid.UUID, ctx: OrgContext = Depends(require(Perm.EXPORT))) -> Response:
    b = svc.get_batch(ctx.db, ctx.org_id, batch_id)
    f, data = svc.file_for(ctx.db, ctx.org_id, b)
    safe_name = "".join(ch for ch in f.original_filename if ch.isalnum() or ch in "._- ") or "source"
    return Response(content=data, media_type="application/octet-stream",
                    headers={"content-disposition": f'attachment; filename="{safe_name}"'})


@router.get("/amendments")
def amendments(ctx: OrgContext = Depends(require(Perm.VIEW))) -> dict:
    from app.services import ledger

    items = []
    for r in svc.pending_amendments(ctx.db, ctx.org_id):
        inv = ledger.get_invoice(ctx.db, ctx.org_id, r.target_id)
        items.append({**row_out(r), "invoice_id": str(inv.id), "invoice_number": inv.invoice_number,
                      "changes": (r.normalised or {}).get("changes", {})})
    return {"items": items}


@router.post("/amendments/{row_id}/approve")
def approve(row_id: uuid.UUID, body: ReviewIn, ctx: OrgContext = Depends(require(Perm.APPROVE_AMENDMENT))) -> dict:
    r = svc.review_amendment(ctx.db, ctx.org, ctx.user.id, row_id, True, body.reason)
    ctx.db.commit()
    return row_out(r)


@router.post("/amendments/{row_id}/reject")
def reject(row_id: uuid.UUID, body: ReviewIn, ctx: OrgContext = Depends(require(Perm.APPROVE_AMENDMENT))) -> dict:
    r = svc.review_amendment(ctx.db, ctx.org, ctx.user.id, row_id, False, body.reason)
    ctx.db.commit()
    return row_out(r)
