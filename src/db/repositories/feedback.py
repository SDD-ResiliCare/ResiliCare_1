from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.feedback import FeedbackInvite, FeedbackSubmission, Review
from src.db.repositories.base import Repository


class FeedbackInviteRepository(Repository[FeedbackInvite]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FeedbackInvite)


class ReviewRepository(Repository[Review]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Review)


class FeedbackRepository(Repository[FeedbackSubmission]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FeedbackSubmission)
