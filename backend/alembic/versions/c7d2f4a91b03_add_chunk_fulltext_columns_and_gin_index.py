"""add chunk fulltext columns and gin index

为 document_chunks 增加应用层分词（jieba）全文检索支持。
- content_tokens：jieba 分词结果（空格拼接），入库侧写入
- content_tsv：STORED 生成列，由 content_tokens 自动推导 tsvector
- GIN 索引：全文检索加速

注意：本迁移只改结构；存量数据的 content_tokens 回填由
scripts/backfill_tokens.py 完成（分词在 Python 侧，SQL 做不了）。
DDL 在单事务内完成，回填失败不影响迁移本身。

Revision ID: c7d2f4a91b03
Revises: b35215880092
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7d2f4a91b03'
down_revision: Union[str, Sequence[str], None] = 'b35215880092'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'document_chunks',
        sa.Column('content_tokens', sa.Text(), nullable=True),
    )
    op.add_column(
        'document_chunks',
        sa.Column(
            'content_tsv',
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(content_tokens, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    # 生成列对存量行会按当前 content_tokens（NULL → 空 tsvector）立即计算；
    # GIN 索引此时建，避免回填后再补建索引
    op.create_index(
        'ix_document_chunks_content_tsv',
        'document_chunks',
        ['content_tsv'],
        unique=False,
        postgresql_using='gin',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_document_chunks_content_tsv',
        table_name='document_chunks',
        postgresql_using='gin',
    )
    op.drop_column('document_chunks', 'content_tsv')
    op.drop_column('document_chunks', 'content_tokens')
