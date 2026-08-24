"""Alembic 迁移入口（异步版本）。

由 `alembic init -t async` 生成，做了两处定制：
1. 用 app.core.config.settings.database_url 覆盖 alembic.ini 里的连接串
2. target_metadata 指向 app.db.base.Base.metadata，便于 autogenerate
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.db.base import Base

# Alembic 配置对象，封装 alembic.ini 里的所有配置项
config = context.config

# 用 settings.database_url 覆盖 alembic.ini 里的连接串，统一从 .env 取
config.set_main_option("sqlalchemy.url", settings.database_url)

# 加载 alembic.ini 中的 [loggers]/[handlers]/[formatters] 配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 后续章节新增 ORM 模型时，确保它们被 import 到此处或 app/db/__init__.py，
# 否则 autogenerate 检测不到表结构变化
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 脚本，不真正连接数据库。

    适用于 CI 里只想检查迁移脚本能否产出，或者把 SQL 交给 DBA 手工执行的场景。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：真正连接数据库执行迁移。

    Alembic 内部用同步 API，所以借助 connection.run_sync 把 do_run_migrations
    跑在 sync 上下文中。
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()