from datetime import datetime
from uuid import UUID

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


class UploadResult(BaseModel):
    id: str | None = None
    name: str
    status: str                 # saved | duplicate | skipped
    reason: str | None = None
    chunks: int = 0


class UploadResponse(BaseModel):
    files: list[UploadResult]