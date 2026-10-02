from pydantic import BaseModel

class QueryRequest(BaseModel):
    question: str
    docs: list[str] = []