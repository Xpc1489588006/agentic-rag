"""问答工作流状态定义。

用 TypedDict 而非 Pydantic：节点函数返回 partial dict、由调用方合并到 state，
比 Pydantic 模型逐字段 copy_update 更轻量，且不需要为每次部分更新做校验。
"""

from typing import Literal, TypedDict
from uuid import UUID

from app.db.models import Message
from app.retrieval.vector_retriever import RetrievedChunk
# 4 选 1 路由策略：original 不改写、rewrite 改写、hyde 假设答案、multi_query 多子查询
QueryRoute = Literal["original", "rewrite", "hyde", "multi_query"]

class RAGState(TypedDict, total=False):
    # 输入
    conversation_id: UUID
    question: str

    # load_context 产出
    chat_history: list[Message]

    # normalize_query 产出（本章 = question）
    query: str
    
    # route_query 产出
    # route：实际采用的策略；query：覆盖 normalize_query 的透传 query（rewrite/hyde 路径下变成改写文本）
    route: QueryRoute
    rewritten_query: str | None
    hyde_answer: str | None
    multi_queries: list[str] | None

    # retrieve 产出
    retrieved_chunks: list[RetrievedChunk]
    # 是否触发拒答（检索不足）。True 时跳过 generate
    refused: bool

    # generate 产出
    answer: str

    # chat_service 落库后回写
    user_message_id: UUID
    assistant_message_id: UUID