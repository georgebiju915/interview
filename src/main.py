from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import engine, Base
from .routes import tasks, sync

# Set up the database tables (simple for development; use migrations in production)
Base.metadata.create_all(bind=engine)

# Create the main FastAPI application
app = FastAPI(title="Task Sync API (local queue + LWW)")
# Enable CORS so the frontend can talk to this API (open to all origins for now)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify ["http://127.0.0.1:5500"] if you want to restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect routes for tasks and sync operations
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(sync.router, prefix="/api/sync", tags=["Sync"])

@app.get("/")
def root():
    """Simple root endpoint to check if the API is running."""
    return {"message": "TaskSync API is running 🚀"}

app.include_router(tasks.router)

app.include_router(sync.router)

@app.get("/api/health")
def health():
    """Health check endpoint."""
    from .utils import now_iso
    return {"status": "ok", "timestamp": now_iso()}

# Catch all unhandled errors and return a clean JSON response
@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    """
    Catch all exceptions and return custom formatted error responses.
    """
    status_code = getattr(exc, "status_code", 500)
    error_message = getattr(exc, "detail", str(exc))

    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": str(request.url.path),
        },
    )