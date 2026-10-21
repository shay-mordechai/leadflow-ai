from fastapi import FastAPI
from src.routers.webhooks import twilio as twilio_webhook_router

app = FastAPI()
app.include_router(twilio_webhook_router.router, prefix="/webhooks/twilio")
