"""add review_chat_id

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inspections", sa.Column("review_chat_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("inspections", "review_chat_id")
