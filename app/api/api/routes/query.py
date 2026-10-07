from fastapi import APIRouter, HTTPException,Depends

from app.api.api.schemas.query import QueryRequest
from app.api.core.async_engine import AsyncEngine
from app.api.dependencies import get_engine,get_chat_store
from storage.postgres.chat import Chat


router = APIRouter(prefix="/api", tags=["query"])

# @router.post("/query")
# async def query():
#     raise HTTPException(501, "Query is not built yet")

@router.post("/query")
async def query_sync(
    req: QueryRequest,
    engine: AsyncEngine = Depends(get_engine),
    chat_store: Chat = Depends(get_chat_store),
):
    
    """Non-streaming query: collects all events and returns final answer."""
    answer = ""
    final_answer = ""
    trace_id = None
    steps = []
    sources = []
    tokens_used = 0
    latency_ms = 0
    confidence = 0.0

    async for event in engine.query_stream(
        req.question,
        confidence_threshold=req.confidence_threshold,
        top_k=req.top_k,
        max_depth=req.max_depth,
        history=req.history,
    ):
        if event.get("type") == "token":
            answer += event.get("token", "")
        elif event.get("type") == "done":
            final_answer = event.get("answer", "")
            trace_id = event.get("trace_id")
            steps = event.get("steps", [])
            sources = event.get("sources", [])
            tokens_used = event.get("tokens_used", 0)
            latency_ms = event.get("latency_ms", 0)
            confidence = event.get("confidence", 0.0)

    answer = answer or final_answer          # use the done answer if no tokens came

    if not answer:
        raise HTTPException(status_code=404, detail="No answer generated")

    await chat_store.save_turn(req.question, answer, sources, confidence, latency_ms)
    
    return {
        "answer": answer,
        "trace_id": trace_id,
        "steps": steps,
        "sources": sources,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
        "confidence": confidence,
    }