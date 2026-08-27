"""存量 chunk 分词回填：迁移加列后跑一次，把历史数据的 content_tokens 补齐。

用法（在 backend 目录下）：
    uv run python scripts/backfill_tokens.py           # 只补未分词的行（幂等）
    uv run python scripts/backfill_tokens.py --force   # 全量重算（分词规则 / 词典变更后用）

说明：
- 分词只能在 Python 侧做（jieba），所以不进 alembic 迁移；
- 生成列 content_tsv 会在 UPDATE 后由数据库自动重算，无需处理；
- 只处理 content_tokens IS NULL 的行，可重复执行（幂等）；
- 逐行 UPDATE + 分批 commit，避免大事务把 GIN 索引写放大堆到一次。
"""

import asyncio
import sys
from pathlib import Path

# scripts/ 不在包内，手动把 backend 根目录加入模块搜索路径，保证从任意位置可执行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update

from app.core.logging import get_logger
from app.db.models import DocumentChunk
from app.db.session import AsyncSessionLocal
from app.ingestion.tokenizer import tokenize_for_index

logger = get_logger(__name__)

BATCH_SIZE = 100


async def backfill(force: bool = False) -> None:
    total = 0
    while True:
        async with AsyncSessionLocal() as session:
            # 每批重新取一批待处理的行，避免一次性把全表加载进内存；
            # force 模式下先清空分词列再重算，保证与新词典 / 规则一致
            stmt = select(DocumentChunk.id, DocumentChunk.content)
            if force:
                stmt = stmt.order_by(DocumentChunk.id).offset(total)
            else:
                stmt = stmt.where(DocumentChunk.content_tokens.is_(None))
            rows = (await session.execute(stmt.limit(BATCH_SIZE))).all()
            if not rows:
                break

            for chunk_id, content in rows:
                await session.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.id == chunk_id)
                    .values(content_tokens=tokenize_for_index(content))
                )
            await session.commit()
            total += len(rows)
            logger.info("backfill progress: %d chunks", total)

    logger.info("backfill done: %d chunks updated", total)


if __name__ == "__main__":
    asyncio.run(backfill(force="--force" in sys.argv))
