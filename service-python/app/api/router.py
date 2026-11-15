from fastapi import APIRouter
from app.api.endpoints import ocr, ml

api_router = APIRouter()
api_router.include_router(ocr.router)
api_router.include_router(ml.router)
