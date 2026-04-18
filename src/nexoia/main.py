from fastapi import FastAPI

from nexoia.interface.http.routers import health


def create_app() -> FastAPI:
    app = FastAPI(title="nexoia-agent", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
