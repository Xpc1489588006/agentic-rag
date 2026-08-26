"""load_context：加载会话上下文。

本章只读取最近 N 条消息塞进 prompt，permissions 留到第 11 章。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.repositories.conversation_repo import ConversationRepository
from app.workflows.rag_state import RAGState


async def load_context(state: RAGState, session: AsyncSession) -> RAGState:
    repo = ConversationRepository(session)
    # 多轮窗口按消息条数粗略截取；第 8 章再做"按完整轮次裁剪 + token 预算控制"
    history = await repo.recent_messages(
        state["conversation_id"], limit=settings.chat_history_window * 2
    )
    return {"chat_history": history}