"""文档入库流水线：解析 → 切分 → 向量化 → 写库 + 状态机。

通过 BackgroundTasks 调度，独立创建 session 以便与请求生命周期解耦。
任意阶段失败都会把 documents.status 置为 FAILED 并写入 error_message。
"""

from uuid import UUID

from app.core.logging import get_logger
from app.db.models import DocumentChunk, DocumentStatus
from app.db.repositories.chunk_repo import DocumentChunkRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.session import AsyncSessionLocal
from app.ingestion import embedder, parser, splitter
from app.ingestion.tokenizer import tokenize_for_index
from app.storage.file_service import get_file_service

logger = get_logger(__name__)


async def _set_status(
    document_id: UUID,
    status: DocumentStatus,
    *,
    error_message: str | None = None,
) -> None:
    """状态变更独立事务：避免长事务、保证前端轮询能立即看到中间态。"""
    async with AsyncSessionLocal() as session:
        repo = DocumentRepository(session)
        await repo.update_status(document_id, status, error_message=error_message)
        await session.commit()


async def ingest_document(document_id: UUID) -> None:
    """执行完整入库流程。"""
    logger.info("ingest start: document_id=%s", document_id)

    try:
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            document = await doc_repo.get_by_id(document_id)
            if document is None:
                logger.warning("document not found, skip ingest: %s", document_id)
                return
            object_key = document.cos_object_key
            filename = document.name

        await _set_status(document_id, DocumentStatus.PARSING)
        content = await get_file_service().download(object_key)
        documents = await parser.parse(filename, content)

        await _set_status(document_id, DocumentStatus.INDEXING)
        chunks = splitter.split(documents)
        if not chunks:
            raise ValueError("切分后没有任何 chunk，请检查文档内容")

        embeddings = await embedder.get_embeddings().aembed_documents(
            [c.page_content for c in chunks]
        )

        async with AsyncSessionLocal() as session:
            chunk_repo = DocumentChunkRepository(session)
            chunk_repo.session.add_all(
                [
                    DocumentChunk(
                        document_id=document_id,
                        content=c.page_content,
                        # 全文检索分词列：与向量同源同批写入，保证两路召回基座一致；
                        # content_tsv 生成列由数据库自动推导，无需显式赋值
                        content_tokens=tokenize_for_index(c.page_content),
                        embedding=vec,
                        page_no=c.metadata.get("page_no"),
                        section_path=c.metadata.get("section_path"),
                        chunk_index=c.metadata["chunk_index"],
                        chunk_hash=c.metadata["chunk_hash"],
                        extra_metadata=c.metadata,
                    )
                    for c, vec in zip(chunks, embeddings, strict=True)
                ]
            )
            await session.commit()

        await _set_status(document_id, DocumentStatus.READY, error_message=None)
        logger.info("ingest done: document_id=%s, chunks=%d", document_id, len(chunks))

    except Exception as exc:
        logger.exception("ingest failed: document_id=%s", document_id)
        # 失败信息直接展示给用户，截断避免超长堆栈污染
        message = str(exc).strip() or exc.__class__.__name__
        await _set_status(document_id, DocumentStatus.FAILED, error_message=message[:500])