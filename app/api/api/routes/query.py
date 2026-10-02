from fastapi import APIRouter
from ..schemas.Query import QueryRequest

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query")
async def query(req: QueryRequest):
    return {
        "answer": f'You asked "{req.question}" using {len(req.docs)} docs: {req.docs}'
    }