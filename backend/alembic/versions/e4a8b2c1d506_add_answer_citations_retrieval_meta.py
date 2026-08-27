"""add answer_citations.retrieval_meta

Revision ID: e4a8b2c1d506
Revises: c7d2f4a91b03
Create Date: 2026-08-27 10:00:00.000000

混合检索调试元数据落库列：sources / vector_rank / keyword_rank /
vector_score / keyword_score / rrf_score，保证历史会话回看与流式回放表现一致。
旧数据为 NULL，前端按缺失隐藏。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4a8b2c1d506"
down_revision: Union[str, Sequence[str], None] = "c7d2f4a91b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "answer_citations",
        sa.Column("retrieval_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("answer_citations", "retrieval_meta")
