"""
OptionsFlow FastAPI Application Entry Point
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 确保从项目根目录加载 .env（uvicorn 的 cwd 可能不同）
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import logging
import traceback

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import CORS_ORIGINS, API_PREFIX, PROJECT_NAME, VERSION
from backend.database import init_db
from backend.routers import auth, options, strategies, agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="Options strategy analysis platform with real-time data and visualization",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(options.router, prefix=API_PREFIX)
app.include_router(strategies.router, prefix=API_PREFIX)
app.include_router(agent.router, prefix=API_PREFIX)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": PROJECT_NAME,
        "version": VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get(f"{API_PREFIX}/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return 500 with logged details"""
    if isinstance(exc, HTTPException):
        raise exc
    tb = traceback.format_exc()
    logger.error("Unhandled exception: %s\n%s", exc, tb)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc),
            "path": str(request.url.path),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
