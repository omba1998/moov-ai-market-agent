# src/main.py
import argparse
import logging
import os
from pathlib import Path

from src.agent import MarketAnalysisAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Moov AI Market Agent (CLI)")
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        required=True,
        help="Produit à analyser (ex: 'iPhone', 'Gaming Laptop')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Chemin du fichier HTML de sortie (optionnel). Exemple: reports/report.html",
    )
    args = parser.parse_args()

    agent = MarketAnalysisAgent()

    result = agent.run(args.query, output_file=args.output)

    if result.get("status") != "success":
        print(f"❌ Error: {result.get('message', 'Unknown error')}")
        raise SystemExit(1)

    report_path = (result.get("report") or {}).get("file_path")
    if not report_path:
        print("❌ Error: Report path missing from agent result.")
        raise SystemExit(1)

    # Pretty output
    abs_path = str(Path(report_path).resolve())
    file_url = f"file://{abs_path}" if os.path.exists(report_path) else None

    print("\n✅ Analyse terminée.")
    print(f"📄 Rapport généré: {report_path}")
    if file_url:
        print(f"🔗 Ouvrir dans le navigateur: {file_url}")


if __name__ == "__main__":
    main()
