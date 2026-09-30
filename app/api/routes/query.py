from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    docs: list[str] = []


@router.post("/query")
async def query(req: QueryRequest):
    return {
        "answer": f'You asked "{req.question}" using {len(req.docs)} docs: {req.docs}'
    }