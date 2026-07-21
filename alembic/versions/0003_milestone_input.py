"""add milestone.input_config_json and milestone_completion.input_value

Revision ID: 0003
Revises: 0002
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("milestone") as batch:
        batch.add_column(sa.Column("input_config_json", sa.Text(), nullable=True))
    with op.batch_alter_table("milestone_completion") as batch:
        batch.add_column(sa.Column("input_value", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("milestone_completion") as batch:
        batch.drop_column("input_value")
    with op.batch_alter_table("milestone") as batch:
        batch.drop_column("input_config_json")
