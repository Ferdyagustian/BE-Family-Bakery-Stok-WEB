from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from app.database import engine
from app.models import User, Store, Product, StoreProduct, Sale, AuditLog
from app.routers import stores, products, forecast, users, audits

app = FastAPI(
    title="Family Bakery API",
    description="Backend API for Family Bakery, including TimesFM forecasting integration.",
    version="1.0.0"
)

from fastapi import Request, Response
# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://family-bakery-stok.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    # OWASP Basic Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(stores.router)
app.include_router(products.router)
app.include_router(forecast.router)
app.include_router(users.router)
app.include_router(audits.router)

@app.on_event("startup")
def on_startup():
    pass 

@app.get("/")
def read_root():
    return {"message": "Welcome to the Family Bakery API"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

