from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.billing import Invoice, InvoiceItem, Payment
from src.db.repositories.base import Repository


class InvoiceRepository(Repository[Invoice]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Invoice)


class InvoiceItemRepository(Repository[InvoiceItem]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, InvoiceItem)


class PaymentRepository(Repository[Payment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)
