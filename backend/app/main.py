from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.routers import extraction, review, clio_auth, health

app = FastAPI(
    title="Richards & Law — Intake Automation",
    description="AI-powered police report extraction and Clio Manage integration",
    version="0.1.0",
)

# CORS — allow Next.js frontend on localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(extraction.router)
app.include_router(review.router)
app.include_router(clio_auth.router)

logger.info("Richards & Law Intake Automation API started")
