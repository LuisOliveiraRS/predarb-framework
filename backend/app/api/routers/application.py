from fastapi import FastAPI

from app.core.settings import settings
from app.core.logger import setup_logger

from app.api.routers.health import router as health_router


def create_app():

    logger = setup_logger()

    logger.info("Starting PredArb Framework")

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )

    app.include_router(health_router)

    @app.get("/")
    def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        }

    return app