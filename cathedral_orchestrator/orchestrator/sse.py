from starlette.responses import StreamingResponse
import asyncio

# SSE helper to forward upstream stream as-is, adding heartbeats and [DONE] terminator if needed.
async def sse_proxy(iter_bytes, content_type: str = "text/event-stream"):
    async def event_iter():
        sent_any = False
        try:
            async for chunk in iter_bytes:
                if not chunk:
                    continue
                sent_any = True
                # Ensure bytes -> str
                if isinstance(chunk, bytes):
                    try:
                        text = chunk.decode("utf-8", errors="ignore")
                    except Exception:
                        text = str(chunk)
                else:
                    text = str(chunk)
                # Pass-through (already formatted 'data: ...\n\n' from upstream LM Studio)
                yield text
        finally:
            # Heartbeat + terminator
            if not sent_any:
                yield "data: {}\n\n"
            yield "data: [DONE]\n\n"
    return StreamingResponse(event_iter(), media_type=content_type)
