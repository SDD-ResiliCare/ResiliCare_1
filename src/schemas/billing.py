"""Invoice and payment contracts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceItemCreate(BaseModel):
    service_code: str
    category: str
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)


class InvoiceCreate(BaseModel):
    invoice_number: str
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    due_at: datetime | None = None
    items: list[InvoiceItemCreate]


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: str
    external_transaction_reference: str | None = None
    paid_at: datetime


class InvoiceDraftUpdate(BaseModel):
    due_at: datetime | None = None


class InvoiceIssue(BaseModel):
    issued_at: datetime


class InvoiceVoid(BaseModel):
    reason: str = Field(min_length=1)


class PaymentRefund(BaseModel):
    refunded_at: datetime
    reason: str = Field(min_length=1)
