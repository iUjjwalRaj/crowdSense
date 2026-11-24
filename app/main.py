import os
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.database import create_tables, database_health


app = FastAPI(title="CrowdSense API", version="0.1.0")
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CROWDSENSE_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
try:
    create_tables()
except Exception:
    logger = logging.getLogger("crowdsense.startup")
    logger.exception("CrowdSense database initialization failed")

logger = logging.getLogger("crowdsense")


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unexpected CrowdSense API error",
        extra={"path": request.url.path, "method": request.method},
    )
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return JSONResponse(
            status_code=503,
            content={
                "status": "service_unavailable",
                "detail": "A required backend service is temporarily unavailable.",
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "status": "internal_error",
            "detail": "An unexpected server error occurred. The server has logged the error.",
        },
    )
