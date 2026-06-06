"""fix_submitted status and return_chat_id

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE inspection_status ADD VALUE IF NOT EXISTS 'fix_submitted'")
    op.add_column("inspections", sa.Column("return_chat_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "inspections",
        sa.Column("fix_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inspections", "fix_submitted_at")
    op.drop_column("inspections", "return_chat_id")
