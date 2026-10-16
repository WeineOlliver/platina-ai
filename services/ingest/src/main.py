from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for startup and shutdown resource management
    (e.g., database connection pools, vector index caches).
    """
    # Startup logic
    yield
    # Shutdown logic (closing db pools, freeing memory)


def create_app() -> FastAPI:
    """
    Application Factory Pattern for FastAPI.
    Enables deterministic isolated testing with TestClient.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Ingestion microservice for PlayStation trophy guides and pgvector semantic retrieval.",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(health_router)

    return app


app = create_app()
