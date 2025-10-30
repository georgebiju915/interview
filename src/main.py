from datetime import datetime

import app
from fastapi import FastAPI,Request
from .database import engine, Base
from .routes import tasks, sync
from fastapi.responses import JSONResponse

from fastapi.middleware.cors import CORSMiddleware


# Create DB tables (simple approach for dev; use Alembic for migrations in prod)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Sync API (local queue + LWW)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify ["http://127.0.0.1:5500"] if you want to restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])

app.include_router(tasks.router)
app.include_router(sync.router)

@app.get("/api/health")
def health():
    from .utils import now_iso
    return {"status": "ok", "timestamp": now_iso()}

@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    # Default error message
    error_message = str(exc)

    # Handle FastAPI's HTTPException separately
    status_code = getattr(exc, "status_code", 500)

    # Use detail if available (for HTTPException)
    if hasattr(exc, "detail"):
        error_message = exc.detail

    # Build the custom error response
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": str(request.url.path)
        },
    )