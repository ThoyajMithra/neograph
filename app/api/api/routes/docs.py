import hashlib
import io
import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pypdf import PdfReader

from ..schemas.document import DocumentFull, DocumentOut

from ..core import document as crud

router = APIRouter(prefix="/api", tags=["docs", "upload"])

ALLOWED = {".txt", ".md", ".pdf"}


def get_pool(request: Request):
    return request.app.state.pool


def extract_text(suffix: str, raw: bytes) -> str:
    """Turn the uploaded bytes into plain text."""
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = raw.decode("utf-8")
    return text.replace("\x00", "")   # Postgres TEXT can't store NUL characters


@router.post("/upload")
def upload(files: List[UploadFile] = File(...), pool=Depends(get_pool)):
    """Returns { files: [{ id, name, status }] }"""
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
        existing = crud.get_by_checksum(pool, checksum)
        if existing:
            results.append({"id": str(existing["id"]), "name": name, "status": "duplicate"})
            continue

        row = crud.insert_document(pool, name, content, checksum)
        results.append({"id": str(row["id"]), "name": name, "status": "saved"})

    return {"files": results}


@router.get("/docs", response_model=list[str])
def list_docs(pool=Depends(get_pool)):
    """Returns just the file names: ["pdf1.pdf", "notes.txt", ...]"""
    return [d["name"] for d in crud.list_documents(pool)]


@router.get("/docs/{doc_id}", response_model=DocumentFull)
def read_doc(doc_id: UUID, pool=Depends(get_pool)):
    row = crud.get_document(pool, doc_id)
    if row is None:
        raise HTTPException(404, "Document not found")
    return row


@router.delete("/docs/{doc_id}")
def remove_doc(doc_id: UUID, pool=Depends(get_pool)):
    if not crud.delete_document(pool, doc_id):
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