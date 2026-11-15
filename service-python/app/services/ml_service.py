from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.schemas.ml import TransactionItem, ClusterSummary, ClusterAnalysisResponse


class MLService:

    @classmethod
    def analyze_clusters(cls, items: List[TransactionItem]) -> ClusterAnalysisResponse:
        total_tx = len(items)

        # Kasus Edge: Data < 3 (Fallback aman)
        if total_tx < 3:
            amounts = [t.amount for t in items]
            min_a = min(amounts) if amounts else 0.0
            max_a = max(amounts) if amounts else 0.0
            avg_a = float(np.mean(amounts)) if amounts else 0.0
            sum_a = sum(amounts) if amounts else 0.0

            transactions_out = []
            for t in items:
                tx_dict = t.model_dump()
                tx_dict["cluster_id"] = 0
                tx_dict["cluster_label"] = "Standar (Belum Terklaster)"
                transactions_out.append(tx_dict)

            summary = [
                ClusterSummary(
                    cluster_id=0,
                    cluster_label="Standar (Belum Terklaster)",
                    count=total_tx,
                    min_amount=min_a,
                    max_amount=max_a,
                    avg_amount=avg_a,
                    total_spent=sum_a
                )
            ] if total_tx > 0 else []

            return ClusterAnalysisResponse(
                success=True,
                total_transactions=total_tx,
                status="fallback",
                clusters_summary=summary,
                transactions=transactions_out,
                insights=[
                    "Data transaksi belum mencukupi (minimal 3 transaksi) untuk menjalankan segmentasi K-Means.",
                    "Terus catat pengeluaran Anda untuk melihat analisis clustering dan profil pengeluaran otomatis."
                ]
            )

        # Kasus Normal: Data >= 3, jalankan StandardScaler + KMeans (3 Klaster)
        df = pd.DataFrame([t.model_dump() for t in items])
        amounts_2d = df[['amount']].values

        scaler = StandardScaler()
        scaled_amounts = scaler.fit_transform(amounts_2d)

        # K-Means dengan k=3
        kmeans = KMeans(n_clusters=3, random_state=42, n_init='auto')
        raw_labels = kmeans.fit_predict(scaled_amounts)

        df['raw_cluster'] = raw_labels

        # Urutkan cluster berdasarkan rata-rata nominal agar label teratur (Rendah -> Sedang -> Tinggi)
        cluster_means = df.groupby('raw_cluster')['amount'].mean().sort_values()
        label_mapping = {}
        cluster_names = [
            "Pengeluaran Ringan (Mikro/Harian)",
            "Pengeluaran Sedang (Rutin/Berkala)",
            "Pengeluaran Besar (Mayor/Signifikan)"
        ]

        for new_id, (old_id, _) in enumerate(cluster_means.items()):
            label_mapping[old_id] = (new_id, cluster_names[new_id])

        df['cluster_id'] = df['raw_cluster'].map(lambda x: label_mapping[x][0])
        df['cluster_label'] = df['raw_cluster'].map(lambda x: label_mapping[x][1])

        # Bangun Ringkasan Tiap Klaster
        clusters_summary: List[ClusterSummary] = []
        for c_id in range(3):
            c_data = df[df['cluster_id'] == c_id]
            if len(c_data) > 0:
                summary = ClusterSummary(
                    cluster_id=c_id,
                    cluster_label=cluster_names[c_id],
                    count=len(c_data),
                    min_amount=float(c_data['amount'].min()),
                    max_amount=float(c_data['amount'].max()),
                    avg_amount=float(round(c_data['amount'].mean(), 2)),
                    total_spent=float(round(c_data['amount'].sum(), 2))
                )
            else:
                summary = ClusterSummary(
                    cluster_id=c_id,
                    cluster_label=cluster_names[c_id],
                    count=0,
                    min_amount=0.0,
                    max_amount=0.0,
                    avg_amount=0.0,
                    total_spent=0.0
                )
            clusters_summary.append(summary)

        # Hasilkan Financial Insights
        total_spending = float(df['amount'].sum())
        insights = []

        high_cluster = clusters_summary[2]
        if high_cluster.count > 0 and total_spending > 0:
            pct_high = round((high_cluster.total_spent / total_spending) * 100, 1)
            insights.append(
                f"Kategori 'Pengeluaran Besar' menyerap {pct_high}% (Rp {high_cluster.total_spent:,.0f}) dari total belanja Anda dengan {high_cluster.count} transaksi."
            )

        low_cluster = clusters_summary[0]
        if low_cluster.count > 0:
            insights.append(
                f"Pengeluaran harian/ringan Anda memiliki rata-rata Rp {low_cluster.avg_amount:,.0f} dengan frekuensi terbanyak ({low_cluster.count} transaksi)."
            )

        # Evaluasi transaksi terbesar
        max_tx = df.loc[df['amount'].idxmax()]
        insights.append(
            f"Transaksi pengeluaran tunggal terbesar adalah '{max_tx.get('description') or max_tx.get('category_name')}' sebesar Rp {max_tx['amount']:,.0f}."
        )

        transactions_out = df.drop(columns=['raw_cluster']).to_dict(orient='records')

        return ClusterAnalysisResponse(
            success=True,
            total_transactions=total_tx,
            status="clustered",
            clusters_summary=clusters_summary,
            transactions=transactions_out,
            insights=insights
        )
