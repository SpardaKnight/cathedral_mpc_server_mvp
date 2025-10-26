from typing import AsyncIterable, Union

import httpx
from starlette.responses import StreamingResponse


async def sse_proxy(
    iter_bytes: AsyncIterable[Union[bytes, str]],
    content_type: str = "text/event-stream",
):
    async def event_iter():
        try:
            async for chunk in iter_bytes:
                if not chunk:
                    continue
                if isinstance(chunk, (bytes, bytearray)):
                    yield bytes(chunk)
                else:
                    yield str(chunk).encode("utf-8")
        except httpx.StreamClosed:
            # Treat upstream EOF as a clean shutdown so clients do not see an error.
            pass
        finally:
            yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_iter(),
        media_type=content_type,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
