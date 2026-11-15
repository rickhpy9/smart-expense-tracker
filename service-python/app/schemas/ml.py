from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TransactionItem(BaseModel):
    id: int
    amount: float
    category_name: Optional[str] = "Umum"
    transaction_date: Optional[str] = None
    description: Optional[str] = None


class ClusterSummary(BaseModel):
    cluster_id: int
    cluster_label: str
    count: int
    min_amount: float
    max_amount: float
    avg_amount: float
    total_spent: float


class ClusterAnalysisResponse(BaseModel):
    success: bool = True
    total_transactions: int
    status: str = Field(..., description="'clustered' jika K-Means dijalankan, 'fallback' jika data < 3")
    clusters_summary: List[ClusterSummary]
    transactions: List[Dict[str, Any]]
    insights: List[str] = Field(default_factory=list, description="Rekomendasi / wawasan finansial")
