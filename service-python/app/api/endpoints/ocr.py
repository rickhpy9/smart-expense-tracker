from fastapi import APIRouter, File, UploadFile, HTTPException, Header, status
from typing import Optional

from app.core.config import settings
from app.schemas.ocr import OCRExtractResponse
from app.services.ocr_service import OCRService

router = APIRouter(prefix="/ocr", tags=["OCR Extraction"])


@router.post(
    "/extract",
    response_model=OCRExtractResponse,
    summary="Ekstraksi teks struk belanja / QRIS",
    description="Menerima upload file gambar struk belanja, melakukan preprocessing OpenCV, inferensi EasyOCR, dan parsing regex."
)
async def extract_receipt_data(
    file: UploadFile = File(..., description="File gambar struk (JPEG, PNG, WEBP)"),
    x_service_token: Optional[str] = Header(None, description="Shared secret token untuk keamanan inter-service")
):
    # Validasi Service Token jika dikirim atau diwajibkan di config
    if settings.SERVICE_TOKEN and x_service_token and x_service_token != settings.SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service token tidak valid."
        )

    # Validasi tipe file
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format file '{file.content_type}' tidak didukung. Harap unggah JPEG, PNG, atau WEBP."
        )

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File gambar kosong."
            )

        result = OCRService.extract_from_image(content)
        return result

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses OCR pada gambar: {str(e)}"
        )
