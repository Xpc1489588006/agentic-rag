"""normalize_query：把原始问题处理成检索 query。

本章直接透传：query = question。第 5 章会引入 Query Rewrite / HyDE / Multi-Query
策略，第 8 章会用最近 N 轮历史增强 query 处理指代和省略。
"""

from app.workflows.rag_state import RAGState


async def normalize_query(state: RAGState) -> RAGState:
    return {"query": state["question"]}