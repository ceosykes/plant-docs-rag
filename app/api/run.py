"""The FastAPI app and its entry point: python -m app.api.run.

Does: mount the routes, set CORS from config, turn every error into one plain sentence, refuse to start without store/.
Does not: expose docs. docs_url, redoc_url and openapi_url are all off.
"""
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app import config
from app.api.routes import router
from app.api.routes_demo import router as demo_router


def check_store_exists() -> None:
    """Fail loudly at startup when the index has not been built."""
    if not config.BM25_PATH.exists():
        raise SystemExit(f"store is missing at {config.STORE_DIR}; run: python -m app.ingest.run")


def plain_error(request: Request, exc: Exception) -> JSONResponse:
    """Every unhandled error becomes {"error": sentence}. Never a stack trace."""
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return JSONResponse(status_code=400, content={"error": f"{exc}. Fix the request and try again."})
    return JSONResponse(status_code=500, content={"error": f"{exc}. Check runs/api.log and retry once."})


def create_app() -> FastAPI:
    """Build the app; called once at import so uvicorn and tests share it."""
    check_store_exists()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router)
    app.include_router(demo_router)
    app.add_exception_handler(HTTPException, plain_error)

    # Catch everything else HERE, inside the CORS layer. The app-level Exception handler runs
    # outside CORS, so its 500 had no CORS headers and the browser showed "Failed to fetch"
    # instead of the sentence. Middleware added later wraps closer to the routes.
    @app.middleware("http")
    async def errors_as_json(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001, the point is to turn anything into a sentence
            return plain_error(request, exc)

    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.api.run:app", host="0.0.0.0", port=config.API_PORT)
