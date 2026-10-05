from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query")
async def query():
    raise HTTPException(501, "Query is not built yet")