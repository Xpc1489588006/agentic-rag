"""业务异常基类与常用异常。

约定：所有业务异常继承 AppException，由 api/error_handlers.py 统一转 HTTP 响应。
后续章节会按需扩展 DocumentNotFoundError / PermissionDeniedError 等具体异常。
"""

from http import HTTPStatus


class AppException(Exception):
    """业务异常基类。"""

    code: str = "internal_error"
    message: str = "服务内部错误"
    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFoundError(AppException):
    code = "not_found"
    message = "资源不存在"
    http_status = HTTPStatus.NOT_FOUND


class PermissionDeniedError(AppException):
    code = "permission_denied"
    message = "无权访问该资源"
    http_status = HTTPStatus.FORBIDDEN


class ConfigurationError(AppException):
    code = "configuration_error"
    message = "服务配置缺失"
    http_status = HTTPStatus.SERVICE_UNAVAILABLE


class ValidationError(AppException):
    code = "validation_error"
    message = "参数校验失败"
    http_status = HTTPStatus.BAD_REQUEST