from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from app.api.api.routes import documents
from app.api.api.routes import query

from storage.database import create_pool,init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    await init_db(app.state.pool)
    yield
    await app.state.pool.close()

app = FastAPI(
    title="neograph",
    description="Knowledge graph RAG",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(query.router)


@app.get("/")
async def root():
    return {"message": "neograph", "docs": "/docs"}