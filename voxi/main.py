from fastapi import FastAPI
from app.api import vapi_routes
from dotenv import load_dotenv
# from app.services.calendar_service import (check_calendar_availability)
import uvicorn

load_dotenv()

app = FastAPI(title="Voxi AI Receptionist")

# Mount Vapi routes
app.include_router(vapi_routes.router)


@app.get("/")
async def root():
    return {"message": "Voxi Server is Live"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
