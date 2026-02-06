from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db import create_db_and_tables


from app.api.v1.routers.general import router as GeneralRouter
from app.api.v1.routers.google_auth import router as GoogleAuthRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Order Scope", lifespan=lifespan)
app.include_router(GeneralRouter)
app.include_router(GoogleAuthRouter)
