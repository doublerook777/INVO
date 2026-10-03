"""FastAPI app. Run: uvicorn app.main:app --reload --port 8000"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import log
from .routes import chat, inventory, whatsapp

app = FastAPI(title="StockSaathi", version="0.1.0",
              description="WhatsApp inventory agent for kirana shops")

# Wide open on purpose -- it's a hackathon demo, and a CORS error at hour 5
# costs more than this risk does.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(inventory.router)
app.include_router(whatsapp.router)


@app.on_event("startup")
def startup():
    db.init_db()
    log("StockSaathi up -- docs at http://localhost:8000/docs")


@app.get("/api/health")
def health():
    return {"ok": True}
