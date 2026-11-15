from typing import List, Optional
from pydantic import BaseModel, Field


class ReceiptParsedData(BaseModel):
    merchant_name: Optional[str] = Field(None, description="Nama toko / merchant hasil ekstraksi")
    total_amount: Optional[float] = Field(None, description="Total nominal transaksi")
    transaction_date: Optional[str] = Field(None, description="Tanggal transaksi (YYYY-MM-DD)")
    suggested_category: Optional[str] = Field(None, description="Rekomendasi kategori pengeluaran")


class OCRExtractResponse(BaseModel):
    success: bool = True
    confidence_score: float = Field(..., description="Rata-rata tingkat keyakinan OCR (0.0 - 1.0)")
    data: ReceiptParsedData
    raw_text: str = Field(..., description="Seluruh teks hasil ekstraksi OCR")
    lines: List[str] = Field(default_factory=list, description="Daftar baris teks yang terbaca")
