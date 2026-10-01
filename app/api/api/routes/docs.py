import os
from typing import List
from fastapi import APIRouter
from pathlib import Path
from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/api", tags=["docs","upload"])

folder_path = Path("storage/docs")

if folder_path:
    os.makedirs(folder_path, exist_ok=True)


@router.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    names = []
    for f in files:
        name = os.path.basename(f.filename)
        with open(folder_path / name, "wb") as out:
            out.write(await f.read())
        names.append(name)
    return {"files": names}

@router.get("/docs")
async def docs():
    documets=[i.name for i in sorted(folder_path.iterdir(),key=lambda f: f.suffix) if i.is_file()]
    return documets