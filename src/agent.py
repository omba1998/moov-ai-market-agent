# src/agent.py
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.tools.web_scraper import WebScraper
from src.tools.market_analyzer import MarketAnalyzer
from src.tools.report_generator import ReportGenerator
from src.tools.sentiment_analyzer import SentimentAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MarketAnalysisAgent:
    """
    Orchestrateur: scrape -> market analysis -> sentiment -> report.
    """

    def __init__(self, reports_dir: str = "reports"):
        self.scraper = WebScraper()
        self.market = MarketAnalyzer()
        self.sentiment = SentimentAnalyzer()
        self.reporter = ReportGenerator(output_dir=reports_dir)

        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def run(self, query: str, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Lance l'analyse complète et retourne un dictionnaire résultat.
        """
        if not query or not query.strip():
            return {"status": "error", "message": "Query is empty."}

        query = query.strip()
        logging.info("🤖 Agent démarré pour query='%s'", query)

        # 1) Collecte produits (scraping + fallback mock)
        products: List[Dict[str, Any]] = self.scraper.fetch_products(query)
        if not products:
            return {"status": "error", "message": "No products found."}

        # 2) Analyse marché (stats + trend + corr + reco)
        market_result: Dict[str, Any] = self.market.analyze_market(products)

        # 3) Choisir "best_product" (recommandation ou fallback)
        best = market_result.get("best_recommendation")
        if isinstance(best, dict) and best:
            best_product: Dict[str, Any] = best
        else:
            best_product = products[0]

        # 4) Sentiment sur le meilleur produit (outil analyse UN produit)
        product_title = best_product.get("title") or best_product.get("name") or query
        product_for_sentiment = {
            "id": best_product.get("id") or "best_reco",
            "title": product_title,
            "rating": best_product.get("rating", 3.0),
            "reviews": best_product.get("reviews") or best_product.get("review_texts"),
        }

        logging.info(
            "🧠 Analyse du sentiment pour : %s (Rating: %s)",
            product_for_sentiment.get("title"),
            product_for_sentiment.get("rating"),
        )

        # IMPORTANT: ton SentimentAnalyzer (que tu as montré) expose analyze(product_name, product)
        sentiment_result = self.sentiment.analyze_product(product_for_sentiment)


        # 5) Construire un payload global cohérent pour le report
        final_analysis: Dict[str, Any] = {
            "query": query,
            "products": products,
            "market": market_result,
            "best_product": best_product,
            "sentiment": sentiment_result,  # le report_generator normalise tout seul
        }

        # 6) Output file
        if output_file is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in query)
            output_file = os.path.join(self.reports_dir, f"market_report_{safe_query}_{ts}.html")

        # 7) Génération report (retourne un path string)
        report_path = self.reporter.generate_report(
            query=query,
            analysis=final_analysis,
            output_path=output_file,
        )


        # 8) Résultat FINAL (report = dict pour main.py)
        result: Dict[str, Any] = {
            "status": "success",
            "query": query,
            "best_product": best_product,
            "market": market_result,
            "sentiment": sentiment_result,
            "report": {"file_path": report_path},
        }
        return result


if __name__ == "__main__":
    agent = MarketAnalysisAgent()
    result = agent.run("iPhone")
    print(result["status"], result.get("report", {}).get("file_path"))
