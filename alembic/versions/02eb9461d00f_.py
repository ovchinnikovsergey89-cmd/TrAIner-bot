"""empty message

Revision ID: 02eb9461d00f
Revises: 93f0aead1bc5
Create Date: 2026-03-07 15:06:34.180408

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02eb9461d00f'
down_revision: Union[str, None] = '93f0aead1bc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
