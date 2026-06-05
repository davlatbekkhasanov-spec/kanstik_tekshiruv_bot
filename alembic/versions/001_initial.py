"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

user_role = sa.Enum("picker", "reviewer", "admin", name="user_role")
inspection_status = sa.Enum("pending", "in_review", "approved", "returned", name="inspection_status")
inspection_result = sa.Enum("correct", "error", name="inspection_result")
error_type = sa.Enum(
    "item_missing",
    "extra_not_on_invoice",
    "wrong_item",
    "wrong_quantity",
    "wrong_store_mixed",
    "incomplete_set",
    "duplicate_item",
    "damaged_item",
    "wrong_color",
    "other",
    name="error_type",
)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    inspection_status.create(op.get_bind(), checkfirst=True)
    inspection_result.create(op.get_bind(), checkfirst=True)
    error_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "inspections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_number", sa.String(64), nullable=False),
        sa.Column("picker_id", sa.BigInteger(), nullable=False),
        sa.Column("picker_name", sa.String(255), nullable=False),
        sa.Column("cargo_photo_file_id", sa.String(255), nullable=False),
        sa.Column("status", inspection_status, nullable=False),
        sa.Column("result", inspection_result, nullable=True),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_name", sa.String(255), nullable=True),
        sa.Column("review_group_message_id", sa.BigInteger(), nullable=True),
        sa.Column("return_group_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["picker_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspections_invoice_number", "inspections", ["invoice_number"])
    op.create_index("ix_inspections_status", "inspections", ["status"])
    op.create_index("ix_inspections_created_at", "inspections", ["created_at"])

    op.create_table(
        "inspection_errors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("inspection_id", sa.BigInteger(), nullable=False),
        sa.Column("error_type", error_type, nullable=False),
        sa.Column("error_comment", sa.Text(), nullable=False),
        sa.Column("error_photo_file_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_id"),
    )
    op.create_index("ix_inspection_errors_error_type", "inspection_errors", ["error_type"])


def downgrade() -> None:
    op.drop_table("inspection_errors")
    op.drop_table("inspections")
    op.drop_table("users")
    error_type.drop(op.get_bind(), checkfirst=True)
    inspection_result.drop(op.get_bind(), checkfirst=True)
    inspection_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
