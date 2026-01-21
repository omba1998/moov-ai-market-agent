# src/tools/report_generator.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Sentiment normalization (robust against nesting + schema variations)
# ---------------------------------------------------------------------

def _pick_best_sentiment_dict(sentiment_data: Any) -> Dict[str, Any]:
    """
    Some pipelines nest details multiple times:
      sentiment_data
        └─ details
            └─ details

    This picks the dict that most likely contains the real distribution/breakdown.
    """
    if not isinstance(sentiment_data, dict):
        return {}

    d0 = sentiment_data
    d1 = d0.get("details") if isinstance(d0.get("details"), dict) else {}
    d2 = d1.get("details") if isinstance(d1.get("details"), dict) else {}

    def has_counts(d: Dict[str, Any]) -> bool:
        return isinstance(d.get("sentiment_breakdown"), dict) or isinstance(d.get("sentiment_distribution"), dict)

    if has_counts(d2):
        return d2
    if has_counts(d1):
        return d1
    return d0


def normalize_sentiment(sentiment_data: Any) -> Dict[str, Any]:
    """
    Normalized schema used by the report generator:
    {
      "average_sentiment": float,
      "sentiment_label": "Positive|Neutral|Negative",
      "sentiment_breakdown": {"positive": int, "neutral": int, "negative": int},
      "key_phrases": [str, ...]
    }
    """
    base = _pick_best_sentiment_dict(sentiment_data)

    # avg
    avg = base.get("average_sentiment_score", None)
    if avg is None:
        avg = base.get("average_sentiment", 0.0)

    # breakdown
    if isinstance(base.get("sentiment_distribution"), dict):
        breakdown = base["sentiment_distribution"]
    elif isinstance(base.get("sentiment_breakdown"), dict):
        breakdown = base["sentiment_breakdown"]
    else:
        breakdown = {"positive": 0, "neutral": 1, "negative": 0}

    # label
    label_raw = base.get("sentiment_label", None)
    if label_raw is None:
        # infer from avg if missing
        try:
            a = float(avg)
        except Exception:
            a = 0.0

        if a >= 0.05:
            label_raw = "positive"
        elif a <= -0.05:
            label_raw = "negative"
        else:
            label_raw = "neutral"

    label_raw = str(label_raw).strip().lower()
    label = "Positive" if label_raw == "positive" else "Negative" if label_raw == "negative" else "Neutral"

    # key phrases (try base, otherwise look at outer object if present)
    key_phrases = base.get("key_phrases") if isinstance(base.get("key_phrases"), list) else []
    if not key_phrases and isinstance(sentiment_data, dict) and isinstance(sentiment_data.get("key_phrases"), list):
        key_phrases = sentiment_data.get("key_phrases") or []
    key_phrases = [str(x) for x in key_phrases if x is not None]

    def _to_int(x: Any, default: int = 0) -> int:
        try:
            return int(x)
        except Exception:
            return default

    def _to_float(x: Any, default: float = 0.0) -> float:
        try:
            return float(x)
        except Exception:
            return default

    return {
        "average_sentiment": _to_float(avg, 0.0),
        "sentiment_label": label,
        "sentiment_breakdown": {
            "positive": _to_int(breakdown.get("positive", breakdown.get("Positive", 0)), 0),
            "neutral": _to_int(breakdown.get("neutral", breakdown.get("Neutral", 0)), 0),
            "negative": _to_int(breakdown.get("negative", breakdown.get("Negative", 0)), 0),
        },
        "key_phrases": key_phrases,
    }


# ---------------------------------------------------------------------
# Market/Analysis helpers (robust against schema variations)
# ---------------------------------------------------------------------

def _safe_get(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return default


def _top_products_from_analysis(analysis: Dict[str, Any], top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Try to extract a list of products from common keys.
    """
    candidates = [
        analysis.get("products"),
        analysis.get("scraped_products"),
        analysis.get("items"),
        analysis.get("data"),
    ]
    products = next((x for x in candidates if isinstance(x, list)), [])
    products = [p for p in products if isinstance(p, dict)]
    return products[:top_n]


def _pricing_summary(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices: List[float] = []
    for p in products:
        price = p.get("price")
        if price is None:
            continue
        try:
            prices.append(float(price))
        except Exception:
            continue

    if not prices:
        return {"count": len(products), "min": None, "max": None, "avg": None}

    return {
        "count": len(products),
        "min": round(min(prices), 2),
        "max": round(max(prices), 2),
        "avg": round(sum(prices) / max(1, len(prices)), 2),
    }


def _bullets_from_key_phrases(key_phrases: List[str], max_items: int = 5) -> List[str]:
    if not key_phrases:
        return ["No strong recurring themes detected in the available reviews."]
    return [f"Recurring theme: <strong>{kp}</strong>" for kp in key_phrases[:max_items]]


# ---------------------------------------------------------------------
# Optional LLM text generation hook
# ---------------------------------------------------------------------

def build_llm_prompt(query: str, analysis: Dict[str, Any], sentiment: Dict[str, Any]) -> str:
    """
    Builds a prompt you can send to any LLM. Keep it short + structured.
    """
    products = _top_products_from_analysis(analysis, top_n=5)
    pricing = _pricing_summary(products)

    return f"""
You are a concise analytics assistant. Write a short executive summary and 3 recommendations.

Context:
- Query: {query}
- Sentiment: label={sentiment.get("sentiment_label")}, avg={sentiment.get("average_sentiment")}
- Sentiment breakdown: {sentiment.get("sentiment_breakdown")}
- Key phrases: {sentiment.get("key_phrases")}
- Pricing summary (from top products): {pricing}

Output format:
Executive Summary:
- (2-4 sentences)

Recommendations:
1) ...
2) ...
3) ...
    
""".strip()

def llm_call_demo(prompt: str) -> str:
    """
    Démo: simule une réponse LLM (sans API) pour prouver l'intégration.
    """
    return (
        "Résumé exécutif:\n"
        "- Le marché est globalement stable, avec quelques variations selon les vendeurs.\n"
        "- Le sentiment est plutôt positif, avec des thèmes récurrents à surveiller.\n\n"
        "Recommandations:\n"
        "1) Aligner le prix autour de la médiane du marché.\n"
        "2) Filtrer les vendeurs selon les retours négatifs récurrents (livraison, batterie, etc.).\n"
        "3) Tester 2-3 offres (bundle / garantie) pour améliorer la conversion.\n"
    )




def fallback_text_summary(query: str, analysis: Dict[str, Any], sentiment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Non-LLM summary generation. Returns:
    { "executive_summary": str, "recommendations": [str, ...] }
    """
    products = _top_products_from_analysis(analysis, top_n=5)
    pricing = _pricing_summary(products)

    label = sentiment.get("sentiment_label", "Neutral")
    avg = float(sentiment.get("average_sentiment", 0.0) or 0.0)
    breakdown = sentiment.get("sentiment_breakdown", {"positive": 0, "neutral": 0, "negative": 0}) or {}
    key_phrases = sentiment.get("key_phrases", []) or []

    exec_summary = (
        f"For the query <strong>{query}</strong>, overall sentiment is <strong>{label}</strong> "
        f"with an average score of <strong>{avg:.2f}</strong>. "
        f"Review distribution: positive={breakdown.get('positive', 0)}, "
        f"neutral={breakdown.get('neutral', 0)}, negative={breakdown.get('negative', 0)}. "
    )

    if pricing.get("avg") is not None:
        exec_summary += (
            f"Observed prices (sample) range from <strong>${pricing['min']}</strong> to <strong>${pricing['max']}</strong>, "
            f"with an average of <strong>${pricing['avg']}</strong>."
        )
    else:
        exec_summary += "Pricing statistics are unavailable from the current dataset."

    recs = [
        "Prioritize listings with strong ratings and consistent positive feedback; verify return policy and warranty.",
        "Compare prices across sellers and target the median/average range unless a premium is justified (condition, storage, accessories).",
        "Watch for recurring issues mentioned in reviews (e.g., battery, shipping) and filter sellers accordingly.",
    ]
    if key_phrases:
        recs.append(f"Focus your checks on recurring themes: {', '.join(key_phrases[:5])}.")

    return {"executive_summary": exec_summary, "recommendations": recs[:4]}


# ---------------------------------------------------------------------
# Report Generator (robust + pretty template)
# ---------------------------------------------------------------------

@dataclass
class ReportGenerator:
    output_dir: str = "reports"
    llm_callable: Optional[Callable[[str], str]] = None  # optional external LLM hook
    enable_llm: bool = False
    llm_timeout_sec: Optional[int] = None  # placeholder for future use

    def generate_report(
        self,
        query: Optional[str] = None,
        analysis: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
        product_name: Optional[str] = None,
        sentiment_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Compatible with existing agent calls.
        - query: preferred name for the report
        - product_name: alias; used if query is missing
        - analysis: global analysis payload (can contain products + market stats)
        - sentiment_data: optional raw sentiment payload
        - **kwargs: ignored safely for backward compatibility
        """
        analysis = analysis or {}
        if not query:
            query = product_name or "market_report"

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        if output_path is None:
            safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in query.lower()).strip("_")
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(self.output_dir) / f"market_report_{safe}_{ts}.html")

        # sentiment: explicit > in analysis > {}
        raw_sentiment = (
            sentiment_data
            or analysis.get("sentiment")
            or analysis.get("sentiment_analysis")
            or analysis.get("sentiment_data")
            or {}
        )
        sentiment_norm = normalize_sentiment(raw_sentiment)

        logger.info(
            "DEBUG sentiment_data (normalized):\n%s",
            json.dumps(sentiment_norm, indent=2, ensure_ascii=False),
        )
        b = sentiment_norm["sentiment_breakdown"]
        logger.info(
            "DEBUG donut counts => positive=%s, neutral=%s, negative=%s",
            b["positive"], b["neutral"], b["negative"],
        )

        narrative = self.generate_narrative_text(query=query, analysis=analysis, sentiment=sentiment_norm)

        html = self._build_html(
            query=query,
            analysis=analysis,
            sentiment=sentiment_norm,
            narrative=narrative,
        )
        Path(output_path).write_text(html, encoding="utf-8")
        return output_path

    def generate_narrative_text(self, query: str, analysis: Dict[str, Any], sentiment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns:
        {executive_summary: str, recommendations: [str, ...], llm_used: bool, llm_error: Optional[str]}
        """
        if not self.enable_llm or self.llm_callable is None:
            out = fallback_text_summary(query=query, analysis=analysis, sentiment=sentiment)
            out.update({"llm_used": False, "llm_error": None})
            return out

        prompt = build_llm_prompt(query=query, analysis=analysis, sentiment=sentiment)
        try:
            text = (self.llm_callable(prompt) or "").strip()
            if not text:
                out = fallback_text_summary(query=query, analysis=analysis, sentiment=sentiment)
                out.update({"llm_used": False, "llm_error": "LLM returned empty text; used fallback."})
                return out

            return {
                "executive_summary": text,
                "recommendations": [],
                "llm_used": True,
                "llm_error": None,
                "llm_prompt": prompt,  # optional debug
            }
        except Exception as e:
            out = fallback_text_summary(query=query, analysis=analysis, sentiment=sentiment)
            out.update({"llm_used": False, "llm_error": str(e)})
            return out

    # ---------------------------
    # Pretty HTML helpers
    # ---------------------------

    def _fmt_money(self, x: Any) -> str:
        try:
            v = float(x)
            return f"${v:,.2f}"
        except Exception:
            return "N/A"

    def _ai_insight_box(self, query: str, analysis: Dict[str, Any], sentiment: Dict[str, Any]) -> str:
        # Try market stats in analysis["market"] else use analysis root
        market = analysis.get("market") if isinstance(analysis.get("market"), dict) else analysis

        avg_price = None
        try:
            avg_price = float(market.get("average_price")) if market.get("average_price") is not None else None
        except Exception:
            avg_price = None

        score = float(sentiment.get("average_sentiment", 0.0) or 0.0)
        label = sentiment.get("sentiment_label", "Neutral")

        if avg_price is None:
            price_comment = "Pricing statistics are unavailable from the current dataset."
        elif avg_price > 500:
            price_comment = "Positioned in a <strong>Premium</strong> segment."
        elif avg_price > 100:
            price_comment = "Positioned in the <strong>mid-market</strong> segment."
        else:
            price_comment = "Positioned in a <strong>budget/entry-level</strong> segment."

        if score > 0.30:
            sentiment_comment = "Customers are strongly positive overall."
            risk_alert = ""
        elif score > 0.0:
            sentiment_comment = "Sentiment is mixed but slightly positive."
            risk_alert = "⚠️ Monitor recurring issues and returns closely."
        else:
            sentiment_comment = "Sentiment suggests potential quality/value concerns."
            risk_alert = "🚨 Investigate negative themes before scaling spend."

        return f"""
        <div class="ai-insight-box">
          <h3 style="margin-top:0;">AI Strategic Analysis <span class="ai-badge">Automated Insight</span></h3>
          <p><strong>Query:</strong> {query}</p>
          <p><strong>Pricing:</strong> {price_comment}</p>
          <p><strong>Sentiment:</strong> {label} (avg={score:.2f}). {sentiment_comment}</p>
          <p class="muted">{risk_alert}</p>
        </div>
        """.strip()

    # ---------------------------
    # Pretty HTML builder
    # ---------------------------

    def _build_html(
        self,
        query: str,
        analysis: Dict[str, Any],
        sentiment: Dict[str, Any],
        narrative: Dict[str, Any],
    ) -> str:
        products = _top_products_from_analysis(analysis, top_n=10)
        pricing = _pricing_summary(products)

        exec_summary = narrative.get("executive_summary", "")
        recs = narrative.get("recommendations", []) or []
        llm_used = narrative.get("llm_used", False)
        llm_error = narrative.get("llm_error", None)

        # Try to get market metrics from analysis if present
        market = analysis.get("market") if isinstance(analysis.get("market"), dict) else analysis

        total_products = market.get("total_products", len(products))
        avg_price = market.get("average_price", pricing.get("avg"))
        median_price = market.get("median_price", None)
        min_price = market.get("min_price", pricing.get("min"))
        max_price = market.get("max_price", pricing.get("max"))
        std_dev = market.get("price_std_dev", None)

        trend = (market.get("market_trend_30d") or {}) if isinstance(market.get("market_trend_30d"), dict) else {}
        trend_label = trend.get("trend", "Stable")
        trend_change = trend.get("change_percentage", "0%")

        best = (market.get("best_recommendation") or {}) if isinstance(market.get("best_recommendation"), dict) else {}
        best_title = best.get("title", "N/A")
        best_price = best.get("price", None)
        best_rating = best.get("rating", None)
        best_source = best.get("source", best.get("platform", "Unknown"))

        corr = (market.get("price_quality_correlation") or {}) if isinstance(market.get("price_quality_correlation"), dict) else {}
        corr_insight = corr.get("insight", "N/A")

        b = sentiment.get("sentiment_breakdown", {"positive": 0, "neutral": 0, "negative": 0})
        pos = int(b.get("positive", 0) or 0)
        neu = int(b.get("neutral", 0) or 0)
        neg = int(b.get("negative", 0) or 0)

        key_phrases = sentiment.get("key_phrases", []) or []
        bullets = _bullets_from_key_phrases(key_phrases, max_items=5)

        def esc(x: Any) -> str:
            s = "" if x is None else str(x)
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        ai_box = self._ai_insight_box(query=query, analysis=analysis, sentiment=sentiment)

        # Ensure JS numeric values
        js_min = float(min_price or 0)
        js_avg = float(avg_price or 0)
        js_max = float(max_price or 0)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Market Analysis Report - {esc(query)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      margin: 0; padding: 0;
      color: #333;
      background-color: #f4f4f9;
    }}
    .container {{
      max-width: 980px;
      margin: 0 auto;
      background: white;
      padding: 40px;
      box-shadow: 0 0 20px rgba(0,0,0,0.08);
    }}
    h1, h2, h3 {{ color: #2c3e50; }}
    .muted {{ color: #7f8c8d; }}
    .cover-page {{
      text-align: center;
      padding: 90px 0;
      page-break-after: always;
      min-height: 70vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 8px;
    }}
    .cover-title {{
      font-size: 3em;
      margin-bottom: 10px;
      color: #2980b9;
      font-weight: 800;
    }}
    .cover-subtitle {{
      font-size: 1.4em;
      color: #7f8c8d;
      margin-bottom: 28px;
    }}
    .section {{
      margin-bottom: 50px;
      padding-bottom: 26px;
      border-bottom: 1px solid #eee;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 18px;
      margin-top: 16px;
    }}
    .kpi-card {{
      background: #f8f9fa;
      padding: 18px;
      border-radius: 10px;
      text-align: center;
      border-left: 5px solid #2980b9;
    }}
    .kpi-value {{
      font-size: 2em;
      font-weight: bold;
      color: #2c3e50;
      margin-bottom: 4px;
    }}
    .kpi-label {{
      font-size: 0.85em;
      color: #7f8c8d;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .chart-container {{
      position: relative;
      height: 320px;
      width: 100%;
      margin-top: 18px;
    }}
    .recommendation-box {{
      background-color: #e8f6f3;
      border: 1px solid #a2d9ce;
      padding: 18px;
      border-radius: 10px;
      margin-top: 14px;
    }}
    .recommendation-title {{
      color: #16a085;
      font-weight: 800;
      margin-bottom: 10px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 18px;
    }}
    th, td {{
      border: 1px solid #ddd;
      padding: 12px;
      text-align: left;
    }}
    th {{
      background-color: #2980b9;
      color: white;
    }}
    tr:nth-child(even) {{
      background-color: #f2f2f2;
    }}
    .executive-summary ul {{
      list-style-type: none;
      padding: 0;
      margin: 16px 0 0 0;
    }}
    .executive-summary li {{
      background: #fff3cd;
      margin: 10px 0;
      padding: 14px;
      border-left: 5px solid #f1c40f;
      font-weight: 600;
    }}
    .footer {{
      text-align: center;
      margin-top: 40px;
      font-size: 0.85em;
      color: #aaa;
    }}
    .ai-insight-box {{
      background-color: #f0f7ff;
      padding: 18px;
      border-left: 5px solid #0056b3;
      border-radius: 8px;
      margin: 18px 0 10px 0;
    }}
    .ai-badge {{
      background: #0056b3;
      color: white;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 0.8em;
      vertical-align: middle;
      margin-left: 8px;
    }}
    .pill {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.85em;
      font-weight: 700;
      background: #eef2ff;
      color: #3730a3;
    }}
    .pill-ok {{ background:#e8f6f3; color:#0f766e; }}
    .pill-warn {{ background:#fff3cd; color:#92400e; }}
    .pill-bad {{ background:#fde2e2; color:#991b1b; }}
    pre {{
      background: #f6f8fa;
      padding: 12px;
      border-radius: 10px;
      overflow: auto;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="cover-page">
      <div class="cover-title">Market Analysis Report</div>
      <div class="cover-subtitle">Strategic Insights for: <strong>{esc(query)}</strong></div>
      <p><strong>Date:</strong> {esc(date_str)}</p>
      <p><strong>Prepared by:</strong> AI Market Agent (Moov AI Edition)</p>
      <p><strong>Mode:</strong> {"LLM" if llm_used else "Deterministic fallback"}{f" • <span class='muted'>LLM error: {esc(llm_error)}</span>" if llm_error else ""}</p>
    </div>

    <div class="section executive-summary">
      <h2>Executive Summary</h2>
      <p class="muted">High-level insights based on the available dataset.</p>
      <ul>
        <li>Market Status: <strong>{esc(trend_label)}</strong> with a {esc(trend_change)} change over the last 30 days.</li>
        <li>Price Point: Average market price is <strong>{esc(self._fmt_money(avg_price))}</strong>.</li>
        <li>Customer Sentiment: Overall is <strong>{esc(sentiment.get("sentiment_label"))}</strong> (avg {float(sentiment.get("average_sentiment", 0.0)):.2f}).</li>
        <li>Top Recommendation: <strong>{esc(best_title)}</strong> at <strong>{esc(self._fmt_money(best_price))}</strong> ({esc(best_source)}).</li>
      </ul>
      <div style="margin-top:14px;">
        {exec_summary}
      </div>
    </div>

    {ai_box}

    <div class="section">
      <h2>Market Overview</h2>
      <p class="muted">Key Performance Indicators extracted from scraped data.</p>
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-value">{esc(total_products)}</div>
          <div class="kpi-label">Products Analyzed</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{esc(self._fmt_money(avg_price))}</div>
          <div class="kpi-label">Average Price</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{esc(self._fmt_money(median_price))}</div>
          <div class="kpi-label">Median Price</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{esc(std_dev) if std_dev is not None else "N/A"}</div>
          <div class="kpi-label">Price Volatility (Std Dev)</div>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>Pricing Analysis</h2>
      <p class="muted">Price distribution and positioning.</p>
      <div class="chart-container">
        <canvas id="priceChart"></canvas>
      </div>
      <p><em>Correlation Insight:</em> {esc(corr_insight)}</p>
    </div>

    <div class="section">
      <h2>Customer Voice & Sentiment</h2>
      <p class="muted">Natural Language Processing summary of review sentiment.</p>

      <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:10px;">
        <span class="pill pill-ok">Positive: {pos}</span>
        <span class="pill pill-warn">Neutral: {neu}</span>
        <span class="pill pill-bad">Negative: {neg}</span>
      </div>

      <div class="chart-container">
        <canvas id="sentimentChart"></canvas>
      </div>

      <h3>Key Feedback Themes</h3>
      <ul>
        {''.join(f"<li>{b}</li>" for b in bullets)}
      </ul>
    </div>

    <div class="section">
      <h2>Recommendations & Action Plan</h2>
      <div class="recommendation-box">
        <div class="recommendation-title">Strategic Recommendation</div>
        <p>Based on the <strong>{esc(trend_label)}</strong> trend and <strong>{esc(sentiment.get("sentiment_label"))}</strong> sentiment:</p>
        <p><strong>Action:</strong> Target the price range around <strong>{esc(self._fmt_money(median_price))}</strong> to <strong>{esc(self._fmt_money(avg_price))}</strong>.</p>
        <p><strong>Opportunity:</strong> Compare sellers (e.g., {esc(best_source)}) where deals like <em>{esc(best_title)}</em> perform well.</p>
      </div>

      <ol>
        {''.join(f"<li>{esc(r)}</li>" for r in recs)}
      </ol>
    </div>

    <div class="section">
      <h2>Top Products (sample)</h2>
      <table>
        <thead>
          <tr>
            <th>Title</th><th>Price</th><th>Rating</th><th>Source</th>
          </tr>
        </thead>
        <tbody>
          {''.join(
            "<tr>"
            f"<td>{esc(_safe_get(p, ['title','name','product_name'], 'N/A'))}</td>"
            f"<td>{esc(self._fmt_money(p.get('price')))}</td>"
            f"<td>{esc(p.get('rating'))}</td>"
            f"<td>{esc(p.get('source'))}</td>"
            "</tr>"
            for p in products
          )}
        </tbody>
      </table>
      <p class="muted" style="margin-top:10px;">Showing up to {len(products)} items from the analysis payload.</p>
    </div>

    <div class="section">
      <h2>Appendix: Methodology</h2>
      <table>
        <tr><th>Component</th><th>Technology</th></tr>
        <tr><td>Data Collection</td><td>Python Requests + BeautifulSoup (Resilient Scraping / Fallback)</td></tr>
        <tr><td>Market Math</td><td>Pandas (Descriptive Stats + Time Series Interpolation)</td></tr>
        <tr><td>NLP Engine</td><td>TextBlob / Lexicon (Polarity Analysis)</td></tr>
        <tr><td>Report Engine</td><td>Dynamic HTML + Chart.js + Deterministic NLG</td></tr>
      </table>
    </div>


    <div class="footer">Generated by AI Market Agent • {esc(date_str)}</div>

    <script>
      // Chart 1: Price Distribution (min/avg/max)
      const ctxPrice = document.getElementById('priceChart').getContext('2d');
      new Chart(ctxPrice, {{
        type: 'bar',
        data: {{
          labels: ['Min Price', 'Average Price', 'Max Price'],
          datasets: [{{
            label: 'Price Points (USD)',
            data: [{js_min}, {js_avg}, {js_max}],
            backgroundColor: ['#3498db', '#2ecc71', '#e74c3c']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false
        }}
      }});

      // Chart 2: Sentiment Donut
      const ctxSent = document.getElementById('sentimentChart').getContext('2d');
      new Chart(ctxSent, {{
        type: 'doughnut',
        data: {{
          labels: ['Positive', 'Neutral', 'Negative'],
          datasets: [{{
            data: [{pos}, {neu}, {neg}],
            backgroundColor: ['#2ecc71', '#95a5a6', '#e74c3c']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false
        }}
      }});
    </script>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------
# Minimal manual test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Simulate the nesting bug you had
    raw_sent = {
        "average_sentiment": 0.0,
        "sentiment_breakdown": {"positive": 0, "neutral": 1, "negative": 0},
        "key_phrases": ["battery", "value", "shipping"],
        "details": {
            "average_sentiment_score": 0.72,
            "sentiment_distribution": {"positive": 18, "neutral": 0, "negative": 0},
            "sentiment_label": "positive",
            "key_phrases": ["battery", "value", "shipping"],
        },
    }

    mock_market = {
        "total_products": 45,
        "average_price": 500.50,
        "median_price": 450.00,
        "min_price": 100,
        "max_price": 1200,
        "price_std_dev": 150.2,
        "market_trend_30d": {"trend": "Rising sharply", "change_percentage": "+5.2%"},
        "best_recommendation": {"title": "Best Value Phone", "price": 400, "rating": 4.4, "source": "Amazon"},
        "price_quality_correlation": {"insight": "Strong link: Higher price = Better quality."},
    }

    rg = ReportGenerator(enable_llm=True, llm_callable=llm_call_demo, output_dir="reports")

    out = rg.generate_report(
        query="iphone 15",
        analysis={
            "market": mock_market,
            "products": [
                {"title": "Example A", "price": 999, "rating": 4.2, "source": "mock"},
                {"title": "Example B", "price": 799, "rating": 4.0, "source": "mock"},
            ],
        },
        sentiment_data=raw_sent,
    )
    print("Wrote:", out)
