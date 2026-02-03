from fastapi import FastAPI
from app.api import vapi_routes

app = FastAPI(title="Voxi AI Receptionist", version="1.0")

app.include_router(vapi_routes.router)
