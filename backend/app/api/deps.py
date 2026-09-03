"""FastAPI 依赖项汇总。

引入认证依赖：
- DbSession：请求级数据库 session
- CurrentUser：解析 Bearer token → User；用户不存在 / 已禁用都翻译成 401
- CurrentAdmin：在 CurrentUser 基础上再加管理员判断
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import User, UserStatus
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_session
from app.services.permission_service import is_admin


def _parse_bearer_token(authorization: str | None) -> str:
    """从 Authorization header 取出 Bearer token；缺失或格式错误统一 401。"""
    if not authorization:
        raise UnauthorizedError("请先登录")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("无效的访问凭证")
    return token


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    """解析 Bearer token，查表拿到 User。

    每个请求都重新查一次而不是把信息塞进 token：
    - 角色 / 状态变更后立即生效，不必等 token 自然过期
    - token 内只放 user_id，泄露 token 也拿不到额外用户信息
    """
    token = _parse_bearer_token(authorization)
    subject = decode_access_token(token)

    try:
        from uuid import UUID

        user_id = UUID(subject)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("无效的访问凭证") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("用户不存在或已被删除")
    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("账号已被禁用")
    return user


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """仅 admin 可通过。普通用户 403。"""
    if not is_admin(user):
        raise PermissionDeniedError("仅管理员可访问")
    return user


DbSession = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
