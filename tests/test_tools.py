# tests/test_tools.py
"""
But: tester chaque outil de manière isolée (unit tests) sans dépendances externes.
- Pas d'internet
- Pas de vraie API
- On vérifie: type de sortie + clés attendues + création du rapport HTML
"""

from pathlib import Path


def test_webscraper_returns_products(monkeypatch):
    """
    WebScraper: doit retourner une liste de produits (dicts).
    Même si le scraping réel échoue, ton scraper a un fallback mock -> la liste ne doit pas être vide.
    """
    from src.tools.web_scraper import WebScraper
    import time

    # Accélère le test (évite le time.sleep(1) dans _try_real_scraping)
    monkeypatch.setattr(time, "sleep", lambda _: None)

    ws = WebScraper()
    products = ws.fetch_products("iphone 15")

    assert isinstance(products, list)
    assert len(products) > 0
    assert isinstance(products[0], dict)
    assert "title" in products[0]
    assert "price" in products[0]


def test_sentiment_analyzer_returns_expected_schema():
    """
    SentimentAnalyzer: doit retourner un dict avec au minimum:
    - average_sentiment
    - sentiment_breakdown
    """
    from src.tools.sentiment_analyzer import SentimentAnalyzer

    sa = SentimentAnalyzer()

    products = [
        {"title": "iPhone 15", "price": 999.0, "rating": 4.6, "source": "mock"},
        {"title": "iPhone 15 (Used)", "price": 700.0, "rating": 4.2, "source": "mock"},
    ]

    sentiment = sa.analyze(products)

    assert isinstance(sentiment, dict)
    assert "average_sentiment" in sentiment
    assert "sentiment_breakdown" in sentiment
    assert isinstance(sentiment["sentiment_breakdown"], dict)

    if "sentiment_label" in sentiment:
        assert sentiment["sentiment_label"] in {"Positive", "Neutral", "Negative"}


def test_market_analyzer_returns_market_summary():
    """
    MarketAnalyzer: ton outil retourne directement un dict `stats`.
    On valide les clés essentielles.
    """
    from src.tools.market_analyzer import MarketAnalyzer

    ma = MarketAnalyzer(seed=42)  # seed pour stabilité si tu veux
    products = [
        {"title": "iPhone 15", "price": 999.0, "rating": 4.6, "source": "mock"},
        {"title": "iPhone 15 (Used)", "price": 700.0, "rating": 4.2, "source": "mock"},
    ]

    stats = ma.analyze_market(products)

    assert isinstance(stats, dict)
    assert "total_products" in stats
    assert "average_price" in stats
    assert "median_price" in stats
    assert "min_price" in stats
    assert "max_price" in stats
    assert "market_trend_30d" in stats
    assert isinstance(stats["market_trend_30d"], dict)


def test_report_generator_creates_html_file(tmp_path):
    """
    ReportGenerator: doit créer un fichier HTML lisible.
    """
    from src.tools.report_generator import ReportGenerator

    rg = ReportGenerator(output_dir=str(tmp_path), enable_llm=False)

    analysis = {
        "market": {
            "total_products": 2,
            "average_price": 850.0,
            "median_price": 850.0,
            "min_price": 700.0,
            "max_price": 1000.0,
            "market_trend_30d": {"trend": "Stable", "change_percentage": "0%"},
            "best_recommendation": {
                "title": "iPhone 15",
                "price": 999.0,
                "rating": 4.6,
                "source": "mock",
            },
            "price_quality_correlation": {"insight": "N/A"},
        },
        "products": [
            {"title": "iPhone 15", "price": 999.0, "rating": 4.6, "source": "mock"},
            {"title": "iPhone 15 (Used)", "price": 700.0, "rating": 4.2, "source": "mock"},
        ],
    }

    sentiment = {
        "average_sentiment": 0.1,
        "sentiment_label": "Positive",
        "sentiment_breakdown": {"positive": 1, "neutral": 1, "negative": 0},
        "key_phrases": ["battery", "camera"],
    }

    out_path = rg.generate_report(query="iphone 15", analysis=analysis, sentiment_data=sentiment)

    p = Path(out_path)
    assert p.exists()

    html = p.read_text(encoding="utf-8")
    assert "Market Analysis Report" in html
    assert "<canvas" in html
    assert "iphone 15" in html.lower()
