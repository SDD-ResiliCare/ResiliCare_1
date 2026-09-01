from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.billing import (
    InvoiceCreate,
    InvoiceDraftUpdate,
    InvoiceIssue,
    InvoiceVoid,
    PaymentCreate,
    PaymentRefund,
)
from src.services.billing_service import BillingService

router = APIRouter(tags=["billing"])
BillingStaff = Annotated[RequestContext, Depends(require_roles("administrator", "billing_staff"))]


@router.post("/encounters/{encounter_id}/invoices", status_code=status.HTTP_201_CREATED)
async def create_invoice(encounter_id: UUID, payload: InvoiceCreate, session: DatabaseSession, context: BillingStaff):
    if context.staff_id is None:
        raise HTTPException(403, "staff identity is required")
    if context.hospital_id is None:
        raise HTTPException(403, "staff hospital identity is required")
    return await BillingService(session).create_invoice(encounter_id, payload, context.staff_id, context.hospital_id)


@router.post("/invoices/{invoice_id}/payments", status_code=status.HTTP_201_CREATED)
async def add_payment(invoice_id: UUID, payload: PaymentCreate, session: DatabaseSession, context: BillingStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "staff hospital identity is required")
    return await BillingService(session).add_payment(invoice_id, payload, context.staff_id, context.hospital_id)


def _hospital_id(context: RequestContext) -> UUID:
    if context.hospital_id is None:
        raise HTTPException(403, "staff hospital identity is required")
    return context.hospital_id


@router.get("/encounters/{encounter_id}/invoices")
async def list_invoices(encounter_id: UUID, session: DatabaseSession, context: BillingStaff):
    return await BillingService(session).list_invoices(encounter_id, _hospital_id(context))


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: UUID, session: DatabaseSession, context: BillingStaff):
    return await BillingService(session).invoice_detail(invoice_id, _hospital_id(context))


@router.patch("/invoices/{invoice_id}/draft")
async def update_invoice_draft(
    invoice_id: UUID, payload: InvoiceDraftUpdate, session: DatabaseSession, context: BillingStaff
):
    return await BillingService(session).update_draft(invoice_id, payload, _hospital_id(context))


@router.post("/invoices/{invoice_id}/issue")
async def issue_invoice(invoice_id: UUID, payload: InvoiceIssue, session: DatabaseSession, context: BillingStaff):
    return await BillingService(session).issue_invoice(invoice_id, payload, _hospital_id(context))


@router.post("/invoices/{invoice_id}/void")
async def void_invoice(invoice_id: UUID, payload: InvoiceVoid, session: DatabaseSession, context: BillingStaff):
    if context.staff_id is None:
        raise HTTPException(403, "staff identity is required")
    return await BillingService(session).void_invoice(invoice_id, payload, context.staff_id, _hospital_id(context))


@router.get("/invoices/{invoice_id}/payments")
async def list_payments(invoice_id: UUID, session: DatabaseSession, context: BillingStaff):
    detail = await BillingService(session).invoice_detail(invoice_id, _hospital_id(context))
    return detail["payments"]


@router.post("/payments/{payment_id}/refund")
async def refund_payment(payment_id: UUID, payload: PaymentRefund, session: DatabaseSession, context: BillingStaff):
    return await BillingService(session).refund_payment(payment_id, payload, _hospital_id(context))
