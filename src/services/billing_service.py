from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.billing import Invoice, InvoiceItem, Payment
from src.db.models.encounter import Encounter
from src.db.repositories.billing import InvoiceItemRepository, InvoiceRepository, PaymentRepository
from src.schemas.billing import (
    InvoiceCreate,
    InvoiceDraftUpdate,
    InvoiceIssue,
    InvoiceVoid,
    PaymentCreate,
    PaymentRefund,
)


class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.invoices = InvoiceRepository(session)
        self.items = InvoiceItemRepository(session)
        self.payments = PaymentRepository(session)

    async def create_invoice(
        self, encounter_id: UUID, payload: InvoiceCreate, staff_id: UUID, hospital_id: UUID
    ) -> Invoice:
        if (
            await self.session.scalar(
                select(Encounter.id).where(Encounter.id == encounter_id, Encounter.hospital_id == hospital_id)
            )
            is None
        ):
            raise HTTPException(404, "encounter not found")
        subtotal = sum(item.quantity * item.unit_price for item in payload.items)
        discount = sum(item.discount_amount for item in payload.items)
        tax = sum(item.tax_amount for item in payload.items)
        grand_total = max(Decimal(0), subtotal - discount + tax)
        invoice = await self.invoices.add(
            Invoice(
                encounter_id=encounter_id,
                invoice_number=payload.invoice_number,
                invoice_version=1,
                status="draft",
                currency_code=payload.currency_code.upper(),
                subtotal=subtotal,
                discount_total=discount,
                tax_total=tax,
                grand_total=grand_total,
                amount_paid=Decimal(0),
                balance_due=grand_total,
                due_at=payload.due_at,
                created_by_staff_id=staff_id,
            )
        )
        for item in payload.items:
            line_total = max(Decimal(0), item.quantity * item.unit_price - item.discount_amount + item.tax_amount)
            await self.items.add(InvoiceItem(invoice_id=invoice.id, line_total=line_total, **item.model_dump()))
        await self.session.commit()
        return invoice

    async def add_payment(
        self, invoice_id: UUID, payload: PaymentCreate, staff_id: UUID | None, hospital_id: UUID
    ) -> Payment:
        invoice = await self.invoices.get(invoice_id, for_update=True)
        if invoice is None:
            raise HTTPException(404, "invoice not found")
        invoice_hospital = await self.session.scalar(
            select(Encounter.hospital_id).where(Encounter.id == invoice.encounter_id)
        )
        if invoice_hospital != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        if payload.amount > invoice.balance_due:
            raise HTTPException(422, "payment exceeds invoice balance")
        payment = await self.payments.add(
            Payment(
                invoice_id=invoice_id,
                received_by_staff_id=staff_id,
                status="succeeded",
                **payload.model_dump(),
            )
        )
        invoice.amount_paid += payload.amount
        invoice.balance_due -= payload.amount
        invoice.status = "paid" if invoice.balance_due == 0 else "partially_paid"
        await self.session.commit()
        return payment

    async def get_invoice(self, invoice_id: UUID, hospital_id: UUID, *, for_update: bool = False) -> Invoice:
        invoice = await self.invoices.get(invoice_id, for_update=for_update)
        if invoice is None:
            raise HTTPException(404, "invoice not found")
        invoice_hospital = await self.session.scalar(
            select(Encounter.hospital_id).where(Encounter.id == invoice.encounter_id)
        )
        if invoice_hospital != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        return invoice

    async def list_invoices(self, encounter_id: UUID, hospital_id: UUID) -> list[Invoice]:
        if (
            await self.session.scalar(
                select(Encounter.id).where(Encounter.id == encounter_id, Encounter.hospital_id == hospital_id)
            )
            is None
        ):
            raise HTTPException(404, "encounter not found")
        return list((await self.session.scalars(select(Invoice).where(Invoice.encounter_id == encounter_id))).all())

    async def invoice_detail(self, invoice_id: UUID, hospital_id: UUID) -> dict:
        invoice = await self.get_invoice(invoice_id, hospital_id)
        items = list(
            (await self.session.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id))).all()
        )
        payments = list((await self.session.scalars(select(Payment).where(Payment.invoice_id == invoice_id))).all())
        return {"invoice": invoice, "items": items, "payments": payments}

    async def update_draft(self, invoice_id: UUID, payload: InvoiceDraftUpdate, hospital_id: UUID) -> Invoice:
        invoice = await self.get_invoice(invoice_id, hospital_id, for_update=True)
        if invoice.status != "draft":
            raise HTTPException(409, "only draft invoices can be edited")
        invoice.due_at = payload.due_at
        await self.session.commit()
        return invoice

    async def issue_invoice(self, invoice_id: UUID, payload: InvoiceIssue, hospital_id: UUID) -> Invoice:
        invoice = await self.get_invoice(invoice_id, hospital_id, for_update=True)
        if invoice.status != "draft":
            raise HTTPException(409, "only draft invoices can be issued")
        invoice.status = "issued"
        invoice.issued_at = payload.issued_at
        await self.session.commit()
        return invoice

    async def void_invoice(self, invoice_id: UUID, payload: InvoiceVoid, staff_id: UUID, hospital_id: UUID) -> Invoice:
        invoice = await self.get_invoice(invoice_id, hospital_id, for_update=True)
        if invoice.amount_paid:
            raise HTTPException(409, "paid invoices must be refunded before voiding")
        invoice.status = "void"
        invoice.voided_at = datetime.now(UTC)
        invoice.void_reason = payload.reason
        invoice.voided_by_staff_id = staff_id
        await self.session.commit()
        return invoice

    async def refund_payment(self, payment_id: UUID, payload: PaymentRefund, hospital_id: UUID) -> Payment:
        payment = await self.payments.get(payment_id, for_update=True)
        if payment is None:
            raise HTTPException(404, "payment not found")
        invoice = await self.get_invoice(payment.invoice_id, hospital_id, for_update=True)
        if payment.status != "succeeded":
            raise HTTPException(409, "only successful payments can be refunded")
        payment.status = "refunded"
        payment.refunded_at = payload.refunded_at
        payment.notes = payload.reason
        invoice.amount_paid -= payment.amount
        invoice.balance_due += payment.amount
        invoice.status = "issued" if invoice.amount_paid == 0 else "partially_paid"
        await self.session.commit()
        return payment
