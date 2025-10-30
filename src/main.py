from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Base, engine
from .routes import tasks, sync
from .utils import now_iso


# ============================================================
# 🚀 FastAPI Application Setup
# ============================================================

app = FastAPI(
    title="Task Sync API",
    version="1.0.0",
    description="A backend API supporting offline task management and sync queueing.",
)

# Create all database tables (for dev only — use Alembic in production)
Base.metadata.create_all(bind=engine)


# ============================================================
# 🌐 CORS Configuration
# ============================================================
# In development, allow all origins.
# For production, replace with frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g., ["https://yourfrontend.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 🔗 API Routers
# ============================================================
# Routes are modular: /api/tasks for CRUD, /api/sync for syncing
app.include_router(tasks.router)
app.include_router(sync.router)


# ============================================================
# 💡 Utility Endpoints
# ============================================================

@app.get("/")
def root():
    """Basic root route — used to confirm the API is alive."""
    return {
        "message": "🚀 Task Sync API is running successfully!",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health")
def health_check():
    """Health check endpoint for uptime monitoring."""
    return {
        "status": "ok",
        "timestamp": now_iso(),
        "environment": "development"
    }


# ============================================================
# ⚠️ Global Exception Handler
# ============================================================

@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions and return a consistent JSON response.
    """
    status_code = getattr(exc, "status_code", 500)
    message = getattr(exc, "detail", str(exc))

    return JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": str(request.url.path),
        },
    )
