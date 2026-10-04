import hashlib
import io
import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pypdf import PdfReader
from docx import Document as DocxDocument

from ..schemas.document import ChunkOut, DocumentFull

from ..core import document as crudd
from ..core import chunking as crudc
from engine.embedding.encoder import chunk_document

router = APIRouter(prefix="/api", tags=["docs", "upload"])

ALLOWED = {".txt", ".md", ".pdf", ".docx"}


def get_pool(request: Request):
    return request.app.state.pool


def extract_text(suffix: str, raw: bytes) -> str:
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(raw))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        doc = DocxDocument(io.BytesIO(raw))
        text = "\n\n".join(p.text for p in doc.paragraphs)
    else:  # .txt, .md
        text = raw.decode("utf-8", errors="replace")
    return text.replace("\x00", "")


@router.post("/upload")
def upload(files: List[UploadFile] = File(...), pool=Depends(get_pool)):
    results = []
    for f in files:
        name = os.path.basename(f.filename or "")
        suffix = os.path.splitext(name)[1].lower()

        if suffix not in ALLOWED:
            results.append({"id": None, "name": name, "status": "skipped", "reason": "unsupported type"})
            continue

        raw = f.file.read()
        try:
            content = extract_text(suffix, raw)
        except Exception:
            results.append({"id": None, "name": name, "status": "skipped", "reason": "could not read file"})
            continue
        if not content.strip():
            results.append({"id": None, "name": name, "status": "skipped",
                            "reason": "no text found (scanned PDF or empty file)"})
            continue

        checksum = hashlib.sha256(raw).hexdigest()
        existing = crudd.get_by_checksum(pool, checksum)
        if existing:
            results.append({"id": str(existing["id"]), "name": name, "status": "duplicate"})
            continue

        chunks = chunk_document(content)
        if not chunks:
            results.append({"id": None, "name": name, "status": "skipped", "reason": "no text found"})
            continue

        doc = crudc.save_document_with_chunks(pool, name, content, checksum, chunks) #inserts both the doc and chunks
        results.append({"id": str(doc["id"]), "name": name, "status": "saved"})
    return {"files": results}


@router.get("/docs", response_model=list[str])
def list_docs(pool=Depends(get_pool)):
    return [d["name"] for d in crudd.list_documents(pool)]


@router.get("/docs/{doc_id}", response_model=DocumentFull)
def read_doc(doc_id: UUID, pool=Depends(get_pool)):
    row = crudd.get_document(pool, doc_id)
    if row is None:
        raise HTTPException(404, "Document not found")
    return row


@router.get("/docs/{doc_id}/chunks", response_model=list[ChunkOut])
def read_chunks(doc_id: UUID, pool=Depends(get_pool)):
    if crudd.get_document(pool, doc_id) is None:
        raise HTTPException(404, "Document not found")
    return crudc.get_chunks(pool, doc_id)


@router.delete("/docs/{doc_id}")
def remove_doc(doc_id: UUID, pool=Depends(get_pool)):
    if not crudd.delete_document(pool, doc_id):
        raise HTTPException(404, "Document not found")
    return {"deleted": True}

# @router.post("/upload")
# async def upload(files: List[UploadFile] = File(...)):
#     names = []
#     for f in files:
#         name = os.path.basename(f.filename)
#         with open(folder_path / name, "wb") as out:
#             out.write(await f.read())
#         names.append(name)
#     return {"files": names}

# @router.get("/docs")
# async def docs():
#     documets=[i.name for i in sorted(folder_path.iterdir(),key=lambda f: f.suffix) if i.is_file()]
#     return documets