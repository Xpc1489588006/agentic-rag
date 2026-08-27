"""中文分词：jieba 应用层分词。

Windows 原生 PostgreSQL 装不了 zhparser（依赖 SCWS、仅 Unix 构建），
因此在入库 / 查询两侧统一用 jieba 分词，切好的词以空格拼接后交给
PostgreSQL 内置 simple 解析器建 tsvector，实现跨平台中文全文检索。

入库与查询必须走同一份分词逻辑，保证两侧词条一致、检索可命中。
"""

from collections.abc import Sequence
from pathlib import Path

import jieba

from app.core.logging import get_logger

logger = get_logger(__name__)

# 业务自定义词典（每行一个词），把"差旅"、"餐补"这类领域词固化为整词，
# 避免被切成"差/旅"导致检索串号；文件不存在则只用 jieba 默认词典
_USER_DICT_PATH = Path(__file__).resolve().parents[2] / "dict" / "user_dict.txt"

_initialized = False
_dict_loaded = False


def _ensure_init() -> None:
    """首次调用时初始化（加载用户词典）；jieba 自身词典惰性加载。"""
    global _initialized, _dict_loaded
    if _initialized:
        return
    if not _dict_loaded and _USER_DICT_PATH.exists():
        jieba.load_userdict(str(_USER_DICT_PATH))
        logger.info("已加载用户词典: %s", _USER_DICT_PATH)
    _dict_loaded = True
    _initialized = True


# 轻量停用词：高频虚词入索引只会膨胀 GIN 且无区分度；需要更全的列表可后续换文件方案。
# 注意 frozenset 必须用显式元素构造，传字符串会被拆成单字符，多字词失效
_STOPWORDS = frozenset(
    "的 了 吗 呢 吧 啊 呀 么 和 与 及 或 者 就 不 都 也 很 还 在 有 没 被 把 对 于"
    " 这个 那个 什么 怎么 因为 所以 如果 但是 然后 以及 一个 我们 他们 自己".split()
)


def tokenize(text: str) -> list[str]:
    """切成词条列表；过滤空白 / 标点 / 停用词。"""
    _ensure_init()
    return [
        w
        for w in jieba.lcut(text)
        if w.strip() and w not in _STOPWORDS and any(c.isalnum() for c in w)
    ]


def tokenize_for_index(text: str) -> str:
    """入库侧：词条以空格拼接，供 to_tsvector('simple', ...) 按词建索引。"""
    return " ".join(tokenize(text))


def tokenize_for_query(text: str) -> Sequence[str]:
    """查询侧：返回词条序列，由检索器拼成 OR 语义的 tsquery。"""
    return tokenize(text)
