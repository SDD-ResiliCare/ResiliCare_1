from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.billing import Invoice, InvoiceItem, Payment
from src.db.models.encounter import Encounter
from src.db.repositories.billing import InvoiceItemRepository, InvoiceRepository, PaymentRepository
from src.schemas.billing import InvoiceCreate, PaymentCreate


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
