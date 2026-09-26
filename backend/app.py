"""FastAPI app composition root."""

import os
from contextlib import asynccontextmanager
from threading import RLock

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import DatabaseConfig, init_db
from backend.prompting import LLMConfig, get_client_wrapper
from backend.routers import actions, auth, code, exercises, feedback, static

def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        load_dotenv()
        app.state.database_config = DatabaseConfig.from_env()
        app.state.active_user_sessions = {}
        app.state.user_lock = RLock()
        app.state.exercises = exercises.load_exercises()
        app.state.llm_config = LLMConfig.from_env()
        app.state.client_wrapper = get_client_wrapper(app.state.llm_config)
        init_db(app.state.database_config)
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

    for route_module in (auth, exercises, code, feedback, actions, static):
        app.include_router(route_module.router)

    return app


app = create_app()


