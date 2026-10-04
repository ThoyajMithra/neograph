from datetime import datetime
from uuid import UUID
from fastapi import Request
from pydantic import BaseModel

class DocumentOut(BaseModel):
    id: UUID
    name: str
    checksum: str
    created_at: datetime
    char_count: int


class DocumentFull(DocumentOut):
    content: str


class ChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    idx: int
    heading: str | None = None
    text: str


