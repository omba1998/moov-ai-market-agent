import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarketAnalyzer:
    def __init__(self, seed: int | None = None):        
        self.rng = np.random.default_rng(seed)

    def analyze_market(self, products_data: List[Dict]) -> Dict:
        """
        Analyse hybride : Stats Descriptives (Mean/Median) + Data Science Avancée (Time Series/Corr).
        """
        if not products_data:
            logging.warning("⚠️ Aucune donnée produit à analyser.")
            return {"error": "No data"}

        logging.info(f"📈 Analyse de marché sur {len(products_data)} produits...")

        # 1. Conversion en DataFrame et Nettoyage de base
        df = pd.DataFrame(products_data)
        
        # Conversion numérique forcée (les erreurs deviennent NaN)
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
        
        # On supprime les produits qui n'ont PAS de prix (inutiles pour l'analyse de marché)
        clean_df = df.dropna(subset=['price'])

        if clean_df.empty:
            return {"error": "No valid price data"}

        # 2. STATISTIQUES DESCRIPTIVES (Mean/Median/Std)
        stats = {
            "total_products": len(clean_df),
            "average_price": round(clean_df['price'].mean(), 2),
            "median_price": round(clean_df['price'].median(), 2), # Robuste aux outliers
            "min_price": float(clean_df['price'].min()),
            "max_price": float(clean_df['price'].max()),
            "price_std_dev": round(clean_df['price'].std(), 2) if len(clean_df) > 1 else 0,
        }

        # 3. CORRÉLATION (Relation Prix vs Note)
        if len(clean_df) > 1 and clean_df['rating'].notna().sum() > 1:
            corr_score = clean_df["price"].corr(clean_df["rating"])
            if pd.isna(corr_score):
                corr_score = 0.0

            stats["price_quality_correlation"] = {
                "score": round(corr_score, 2) if not pd.isna(corr_score) else 0,
                "insight": self._interpret_correlation(corr_score)
            }

        # 4. TIME SERIES & GESTION DES MANQUANTS (Simulation Senior)
        stats["market_trend_30d"] = self._simulate_and_analyze_trend(clean_df)

        # 5. BEST VALUE (Recommandation)
        best_deals = clean_df.dropna(subset=["rating"])
        best_deals = best_deals[best_deals["rating"] >= 4.0].sort_values(by="price")

        if not best_deals.empty:
            top = best_deals.iloc[0]
            stats["best_recommendation"] = {
                "title": top['title'],
                "price": float(top['price']),
                "rating": float(top['rating']),
                "source": top.get('source', 'Unknown')
            }
        else:
            stats["best_recommendation"] = None

        logging.info("✅ Analyse terminée.")
        return stats

    def _interpret_correlation(self, score: float) -> str:
        """Traduit les maths en phrase pour l'IA."""
        if pd.isna(score): return "Not enough data."
        if score > 0.6: return "Strong link: Higher price = Better quality."
        if score < -0.2: return "Negative link: Expensive items aren't necessarily better."
        return "No clear link between price and quality."

    def _simulate_and_analyze_trend(self, current_df: pd.DataFrame) -> Dict:
        """
        Simule un historique de 30 jours avec des données manquantes (NaN)
        et démontre l'utilisation de l'interpolation.
        """
        dates = [datetime.now() - timedelta(days=i) for i in range(30)]
        dates.reverse()
        
        avg_price_now = current_df['price'].mean()
        historical_prices = []

        # Simulation de données sales (avec des trous)
        for _ in range(30):
            if self.rng.random() < 0.1: # 10% de chance de trou
                historical_prices.append(np.nan)
            else:
                noise = self.rng.uniform(0.9, 1.1)
                historical_prices.append(avg_price_now * noise)

        ts_df = pd.DataFrame({'date': dates, 'price': historical_prices})
        ts_df.set_index('date', inplace=True)

        # INTERPOLATION (La touche Pro)
        missing_count = ts_df['price'].isna().sum()
        ts_df['price'] = ts_df['price'].interpolate(method='linear').bfill().ffill()

        start = ts_df['price'].iloc[0]
        end = ts_df['price'].iloc[-1]
        change_pct = ((end - start) / start) * 100

        trend = "Stable"
        if change_pct > 5: trend = "Rising sharply 📈"
        elif change_pct < -5: trend = "Dropping significantly 📉"

        return {
            "trend": trend,
            "change_percentage": f"{round(change_pct, 2)}%",
            "missing_data_points_repaired": int(missing_count)
        }

if __name__ == "__main__":
    # Test rapide
    analyzer = MarketAnalyzer()
    mock_data = [
        {"title": "iPhone 15", "price": 999, "rating": 4.5},
        {"title": "iPhone 15 Pro", "price": 1200, "rating": 4.8},
        {"title": "Bad Phone", "price": 300, "rating": 2.0}
    ]
    import json
    print(json.dumps(analyzer.analyze_market(mock_data), indent=2))
