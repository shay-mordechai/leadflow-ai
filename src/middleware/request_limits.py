"""Request body and JSON nesting limits for untrusted HTTP input."""

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse

ASGIApp = Callable[..., Awaitable[None]]


class _RequestRejected(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class RequestBodyLimitMiddleware:
    """Enforce streaming body-size limits and a shallow JSON nesting bound."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int = 1024 * 1024,
        max_multipart_body_size: int = 26 * 1024 * 1024,
        max_json_depth: int = 64,
        upload_path_prefix: str = "/api/v1/sessions/upload/",
    ) -> None:
        self.app = app
        self.max_body_size = max_body_size
        self.max_multipart_body_size = max_multipart_body_size
        self.max_json_depth = max_json_depth
        self.upload_path_prefix = upload_path_prefix

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        path = scope.get("path", "")
        is_audio_upload = (
            path.startswith(self.upload_path_prefix)
            and content_type == b"multipart/form-data"
        )
        body_limit = (
            self.max_multipart_body_size if is_audio_upload else self.max_body_size
        )
        is_json = content_type == b"application/json" or content_type.endswith(b"+json")

        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await self._reject(scope, receive, send, 400, "Invalid Content-Length")
                return
            if declared_length < 0:
                await self._reject(scope, receive, send, 400, "Invalid Content-Length")
                return
            if declared_length > body_limit:
                await self._reject(scope, receive, send, 413, "Request body too large")
                return

        received_bytes = 0
        json_depth = 0
        in_string = False
        escaped = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes, json_depth, in_string, escaped
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received_bytes += len(chunk)
                if received_bytes > body_limit:
                    raise _RequestRejected(413, "Request body too large")

                if is_json:
                    for byte in chunk:
                        if in_string:
                            if escaped:
                                escaped = False
                            elif byte == 0x5C:
                                escaped = True
                            elif byte == 0x22:
                                in_string = False
                        elif byte == 0x22:
                            in_string = True
                        elif byte in (0x7B, 0x5B):
                            json_depth += 1
                            if json_depth > self.max_json_depth:
                                raise _RequestRejected(
                                    400,
                                    "JSON nesting depth exceeds limit",
                                )
                        elif byte in (0x7D, 0x5D):
                            json_depth = max(0, json_depth - 1)
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestRejected as rejection:
            await self._reject(
                scope,
                receive,
                send,
                rejection.status_code,
                rejection.detail,
            )

    @staticmethod
    async def _reject(
        scope: dict[str, Any],
        receive: Any,
        send: Any,
        status_code: int,
        detail: str,
    ) -> None:
        response = JSONResponse(status_code=status_code, content={"detail": detail})
        await response(scope, receive, send)
