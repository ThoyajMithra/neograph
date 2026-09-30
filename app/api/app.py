from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import query


app = FastAPI(
    title="neograph",
    description="Knowledge graph RAG",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)


@app.get("/")
async def root():
    return {"message": "neograph", "docs": "/docs"}