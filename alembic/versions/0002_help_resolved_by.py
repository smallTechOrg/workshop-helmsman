"""add help_request.resolved_by

Revision ID: 0002
Revises: 0001
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("help_request") as batch:
        batch.add_column(sa.Column("resolved_by", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("help_request") as batch:
        batch.drop_column("resolved_by")
