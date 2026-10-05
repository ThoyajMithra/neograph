from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.api.schemas.documents import ChunkOut, DocumentFull, UploadResponse
from app.api.core.async_engine import AsyncEngine
from app.api.dependencies import get_engine

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload(files: List[UploadFile] = File(...),engine: AsyncEngine = Depends(get_engine)):
    payload = [(f.filename or "", await f.read()) for f in files]
    return {"files": await engine.ingest_files(payload)}


@router.get("/docs", response_model=list[str])
async def list_docs(engine: AsyncEngine = Depends(get_engine)):
    """Just the file names, which is what the frontend expects."""
    return [d["name"] for d in await engine.list_documents()]


@router.get("/docs/{doc_id}", response_model=DocumentFull)
async def read_doc(doc_id: UUID, engine: AsyncEngine = Depends(get_engine)):
    doc = await engine.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/docs/{doc_id}/chunks", response_model=list[ChunkOut])
async def read_chunks(doc_id: UUID, engine: AsyncEngine = Depends(get_engine)):
    if await engine.get_document(doc_id) is None:
        raise HTTPException(404, "Document not found")
    return await engine.get_chunks(doc_id)


@router.delete("/docs/{doc_id}")
async def remove_doc(doc_id: UUID, engine: AsyncEngine = Depends(get_engine)):
    if not await engine.delete_document(doc_id):
        raise HTTPException(404, "Document not found")
    return {"deleted": True}