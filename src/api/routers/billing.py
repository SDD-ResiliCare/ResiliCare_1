from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.billing import InvoiceCreate, PaymentCreate
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
