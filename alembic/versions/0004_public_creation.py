"""add workshop.creator_email and workshop.created_via (Phase 6 public creation)

Revision ID: 0004
Revises: 0003
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workshop") as batch:
        batch.add_column(sa.Column("creator_email", sa.String(254), nullable=True))
        # server_default backfills every pre-existing row to 'admin' in place.
        batch.add_column(
            sa.Column("created_via", sa.String(16), nullable=False, server_default="admin")
        )


def downgrade() -> None:
    with op.batch_alter_table("workshop") as batch:
        batch.drop_column("created_via")
        batch.drop_column("creator_email")
