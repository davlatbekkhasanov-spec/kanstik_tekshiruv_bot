from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import ErrorType, InspectionResult, InspectionStatus, UserRole
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.picker, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    picker_inspections: Mapped[list["Inspection"]] = relationship(
        back_populates="picker",
        foreign_keys="Inspection.picker_id",
    )


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(64), index=True)
    picker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    picker_name: Mapped[str] = mapped_column(String(255))
    cargo_photo_file_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus), default=InspectionStatus.pending, index=True
    )
    result: Mapped[InspectionResult | None] = mapped_column(Enum(InspectionResult), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_group_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    return_group_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    picker: Mapped[User] = relationship(back_populates="picker_inspections", foreign_keys=[picker_id])
    error: Mapped["InspectionError | None"] = relationship(back_populates="inspection", uselist=False)


class InspectionError(Base):
    __tablename__ = "inspection_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inspections.id", ondelete="CASCADE"), unique=True, index=True
    )
    error_type: Mapped[ErrorType] = mapped_column(Enum(ErrorType), index=True)
    error_comment: Mapped[str] = mapped_column(Text)
    error_photo_file_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    inspection: Mapped[Inspection] = relationship(back_populates="error")
