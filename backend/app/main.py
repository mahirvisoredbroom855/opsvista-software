# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import traceback

app = FastAPI(title="OpsVista API", version="0.1.0")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ Validation error:")
    traceback.print_exc()
    print("Body received:", exc.body)
    print("Validation details:", exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 Finance feature router will be added here later
# from app.features.finance.router import router as finance_router
# app.include_router(finance_router, prefix="/api/v1/finance")

@app.get("/")
async def root():
    return {"message": "OpsVista API - Finance Feature"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "feature": "finance"}
