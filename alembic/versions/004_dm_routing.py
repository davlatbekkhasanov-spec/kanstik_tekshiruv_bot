"""reviewer and picker DM message routing

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inspections", sa.Column("reviewer_dm_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("inspections", sa.Column("reviewer_dm_message_id", sa.BigInteger(), nullable=True))
    op.add_column("inspections", sa.Column("picker_return_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("inspections", sa.Column("picker_return_message_id", sa.BigInteger(), nullable=True))
    op.add_column("inspections", sa.Column("confirm_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("inspections", sa.Column("confirm_message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("inspections", "confirm_message_id")
    op.drop_column("inspections", "confirm_chat_id")
    op.drop_column("inspections", "picker_return_message_id")
    op.drop_column("inspections", "picker_return_chat_id")
    op.drop_column("inspections", "reviewer_dm_message_id")
    op.drop_column("inspections", "reviewer_dm_chat_id")
