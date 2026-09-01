"""Review and feedback contracts."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReviewCreate(BaseModel):
    review_target: str
    reviewed_staff_id: UUID | None = None
    overall_rating: int = Field(ge=1, le=5)
    dimension_ratings: dict[str, int] = Field(default_factory=dict)
    would_recommend: bool | None = None
    review_text: str | None = Field(default=None, max_length=4000)
    is_anonymous_publicly: bool = True

    @model_validator(mode="after")
    def validate_target(self) -> "ReviewCreate":
        if self.review_target == "hospital" and self.reviewed_staff_id is not None:
            raise ValueError("hospital reviews cannot specify reviewed_staff_id")
        if self.review_target == "doctor" and self.reviewed_staff_id is None:
            raise ValueError("doctor reviews require reviewed_staff_id")
        if self.review_target not in {"hospital", "doctor"}:
            raise ValueError("review_target must be hospital or doctor")
        return self


class ReviewSubmission(ReviewCreate):
    token: str = Field(min_length=32, max_length=512)


class FeedbackCreate(BaseModel):
    hospital_id: UUID
    encounter_id: UUID | None = None
    category: str
    rating: int | None = Field(default=None, ge=1, le=5)
    message: str = Field(min_length=1, max_length=8000)
    contact_permission: bool = False
