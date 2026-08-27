"""混合检索冒烟验证：回填完整性 + HybridRetriever 融合 + 拒答判定。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.config import settings
from app.db.models import DocumentChunk
from app.db.session import AsyncSessionLocal
from app.retrieval.hybrid_retriever import HybridRetriever


async def main() -> None:
    async with AsyncSessionLocal() as session:
        total = (
            await session.execute(select(func.count(DocumentChunk.id)))
        ).scalar_one()
        missing = (
            await session.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.content_tokens.is_(None)
                )
            )
        ).scalar_one()
        print(f"[backfill] total={total} missing_tokens={missing}")

    query = "早上睡过头导致上班迟到半小时会有什么后果"
    retriever = HybridRetriever()
    chunks = await retriever.search(
        query,
        recall_top_k=settings.retrieval_recall_top_k,
        final_top_k=settings.retrieval_top_k,
    )
    print(f"[hybrid] hits={len(chunks)}")
    for c in chunks:
        print(
            f"  rrf={c.rrf_score:.4f} sources={'+'.join(c.sources)} "
            f"vec_rank={c.vector_rank} vec={c.vector_score} "
            f"kw_rank={c.keyword_rank} kw={c.keyword_score} "
            f"doc={c.document_name} :: {c.content[:30]}"
        )

    # 拒答判定预演：与 retrieve 节点 _should_refuse 同逻辑（双路印证放行）
    if not chunks:
        refused = True
    else:
        top = chunks[0]
        if top.vector_score is not None and top.keyword_score is not None:
            refused = False
        elif top.vector_score is None:
            refused = True
        else:
            refused = top.vector_score < settings.retrieval_min_score
    top_vec = chunks[0].vector_score if chunks else None
    print(f"[refusal] top_vector_score={top_vec} refused={refused}")


if __name__ == "__main__":
    asyncio.run(main())
