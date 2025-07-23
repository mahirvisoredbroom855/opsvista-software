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


# ⬇️  existing feature routers
from app.features.task_assignment.api.v1.tasks import router as task_router

# ⬇️  NEW – logout /auth endpoints ---------------------------
from app.features.task_assignment.api.v1.sessions import router as auth_router
# ------------------------------------------------------------

app = FastAPI(title="OpsVista API", version="0.1.0")


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



# (optional) CORS — keep if you already have it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⬇️  include all routers
app.include_router(task_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")   # 🚀 now /api/v1/auth/logout works




