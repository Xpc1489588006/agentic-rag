"""retrieve：执行向量 + 关键词混合检索（RRF 融合），并判断是否触发拒答。

HybridRetriever 内部双 session 并发召回两路 → RRF 融合 → 取 final_top_k。

multi_query 路径下每个子查询独立做一次 hybrid 检索，再朴素合并去重；
不在子查询之间再做嵌套 RRF。

拒答规则（以融合 Top1 为准，不再看单路各自的最高分）：
- Top1 双路同时命中（vector + keyword）→ 语义与关键词互相印证，直接放行
- Top1 仅命中向量路 → cosine sim 低于阈值则拒答（与单路时代同语义）
- Top1 仅命中关键词路 → 缺乏语义佐证，拒答
- 用向量分数而不是 RRF 分数做阈值，因为 RRF 是相对排名分，绝对值在不同 query 下可比性差

为什么双路命中直接放行：本项目关键词路是 jieba + 先严后宽，"迟到半小时"这类口语问题
向量分 0.514 不够 0.6，但关键词精确命中《考勤与请假制度》2.2 节，双路印证后放行。
"""

from app.core.config import settings
from app.llm.prompts import REFUSAL_ANSWER
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.vector_retriever import RetrievedChunk
from app.workflows.rag_state import RAGState


async def retrieve(state: RAGState) -> RAGState:
    retriever = HybridRetriever()
    recall_top_k = settings.retrieval_recall_top_k
    final_top_k = settings.retrieval_top_k

    if state.get("route") == "multi_query" and state.get("multi_queries"):
        # 各子查询独立走 hybrid 检索，再合并；不做嵌套 RRF
        bundles: list[list[RetrievedChunk]] = []
        for sub_query in state["multi_queries"] or []:
            bundles.append(
                await retriever.search(
                    sub_query,
                    recall_top_k=recall_top_k,
                    final_top_k=final_top_k,
                )
            )
        chunks = _merge_chunks(bundles, top_k=final_top_k)
    else:
        chunks = await retriever.search(
            state["query"],
            recall_top_k=recall_top_k,
            final_top_k=final_top_k,
        )

    refused = _should_refuse(chunks)
    update: RAGState = {
        "retrieved_chunks": chunks,
        "refused": refused,
    }
    if refused:
        update["answer"] = REFUSAL_ANSWER
    return update


def _should_refuse(chunks: list[RetrievedChunk]) -> bool:
    """混合检索后的拒答判定，仅看 Top1 的相关度。

    双路同时命中视作互相印证直接放行；单路命中时回到各自的可信判据：
    向量路看 cosine 阈值，关键词路缺乏语义佐证一律拒答。
    """
    if not chunks:
        return True
    top = chunks[0]
    if top.vector_score is not None and top.keyword_score is not None:
        return False  # 双路印证：语义相关且关键词精确命中
    if top.vector_score is None:
        return True  # Top1 仅命中关键词路，缺乏语义佐证
    return top.vector_score < settings.retrieval_min_score


def _merge_chunks(
    bundles: list[list[RetrievedChunk]], top_k: int
) -> list[RetrievedChunk]:
    """multi_query 子查询结果合并：去重 + 取 Top-K。

    同一个 chunk 可能在多条子查询中都命中；保留 RRF 分最高的那条，
    再整体按 RRF 分降序取前 top_k。
    """
    best: dict[str, RetrievedChunk] = {}
    for bundle in bundles:
        for chunk in bundle:
            key = str(chunk.chunk_id)
            prev = best.get(key)
            if prev is None or (chunk.rrf_score or 0.0) > (prev.rrf_score or 0.0):
                best[key] = chunk
    ranked = sorted(best.values(), key=lambda c: c.rrf_score or 0.0, reverse=True)
    return ranked[:top_k]
