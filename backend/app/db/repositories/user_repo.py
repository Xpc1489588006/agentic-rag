"""users 表访问层。

约定同其它 repo：不负责 commit，事务边界由 service 控制。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        # roles 走 lazy="selectin" 自动预加载，这里 session.get 直接拿即可
        return await self.session.get(User, user_id)

    async def get_fresh(self, user_id: UUID) -> User | None:
        """commit 后重新查一次，确保列属性与 roles 都是新鲜值。

        commit 默认会把对象全部属性置为 expired；如果只 refresh 关系
        （attribute_names=["roles"]）列属性仍是过期态，序列化时同步访问
        会触发隐式 IO 报 MissingGreenlet。这里用显式 selectinload 一次查齐。
        """
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = (
            select(User)
            .where(User.username == username)
            .options(selectinload(User.roles))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_all(self) -> int:
        """启动期种子初始化用：库内无用户时才建 admin。"""
        return int(
            (await self.session.execute(select(func.count(User.id)))).scalar_one()
        )

    async def list_paginated(self, page: int, page_size: int) -> tuple[list[User], int]:
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        offset = (page - 1) * page_size
        items_stmt = (
            select(User)
            .order_by(User.created_at.asc(), User.id.asc())
            .offset(offset)
            .limit(page_size)
            .options(selectinload(User.roles))
        )
        count_stmt = select(func.count(User.id))
        items = (await self.session.execute(items_stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return list(items), int(total)

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.flush()

    async def set_roles(self, user: User, roles: list[Role]) -> None:
        """整体替换用户角色集合。"""
        user.roles = roles
        await self.session.flush()
