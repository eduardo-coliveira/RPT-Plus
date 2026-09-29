"""Set up the FastAPI application and its routes."""

import os
from contextlib import asynccontextmanager
from threading import RLock

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import DatabaseConfig, initialize_database
from backend.prompting import LLMConfig, create_llm_client
from backend.routers import actions, auth, code_submissions, exercises, feedback, static

def create_app() -> FastAPI:
    """Create the application and register its routes."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Load configuration and start the shared services."""

        load_dotenv()
        app.state.database_config = DatabaseConfig.from_env()
        app.state.active_user_sessions = {}
        app.state.user_lock = RLock()
        # app.state.exercises = exercises.load_exercise_catalog()
        app.state.exercises = exercises.load_exercise_catalog("csharp")
        app.state.llm_config = LLMConfig.from_env()
        app.state.client_wrapper = create_llm_client(app.state.llm_config)
        initialize_database(app.state.database_config)
        yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(static.DIST_DIR, "assets")),
        name="assets",
    )

    for route_module in (auth, exercises, code_submissions, feedback, actions, static):
        app.include_router(route_module.router)

    return app


app = create_app()


