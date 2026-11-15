from fastapi import APIRouter, HTTPException, Header, status
from typing import List, Optional

from app.core.config import settings
from app.schemas.ml import TransactionItem, ClusterAnalysisResponse
from app.services.ml_service import MLService

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post(
    "/cluster",
    response_model=ClusterAnalysisResponse,
    summary="K-Means Clustering Transaksi Finansial",
    description="Menerima list transaksi historis pengguna, melakukan scaling normalisasi, dan mengelompokkan ke dalam 3 klaster pengeluaran dengan wawasan finansial."
)
async def cluster_transactions(
    transactions: List[TransactionItem],
    x_service_token: Optional[str] = Header(None, description="Shared secret token untuk keamanan inter-service")
):
    if settings.SERVICE_TOKEN and x_service_token and x_service_token != settings.SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service token tidak valid."
        )

    try:
        response = MLService.analyze_clusters(transactions)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat menjalankan analisis klaster: {str(e)}"
        )
