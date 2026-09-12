from agents import set_default_openai_key
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api, health
from app.config import settings

app = FastAPI(title="Agentic Workbench API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(api.router)

set_default_openai_key(settings.openai_api_key)
