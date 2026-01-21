# sentiment_analyzer.py
import logging
import math
import random
import re
from typing import Dict, List, Tuple

# Robustesse: TextBlob optionnel
try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from typing import Dict, Any, Optional

class SentimentAnalyzer:
    """
    Objectif:
    - Générer une distribution "raisonnable" d'avis (positive/neutral/negative) basée sur le rating.
    - Scorer chaque avis avec une combinaison: rating + texte (TextBlob ou lexique) + bruit.
    - Retourner moyenne + label global + distribution + % + échantillon d'avis scorés.

    IMPORTANT:
    - Les clés de distribution sont en minuscules: 'positive', 'neutral', 'negative'
      (évite le bug "je ne vois que neutral" si le rapport attend ces clés).
    """

    def __init__(
        self,
        n_reviews: int = 18,
        seed: int | None = None,
        rating_weight: float = 0.30,
        text_weight: float = 0.65,
        noise_weight: float = 0.05,
        neutral_band: float = 0.15,

        enforce_diversity: bool = True,
        min_each_class: int = 1,
    ):
        self.n_reviews = max(3, int(n_reviews))
        self.seed = seed
        self.rating_weight = float(rating_weight)
        self.text_weight = float(text_weight)
        self.noise_weight = float(noise_weight)
        self.neutral_band = float(neutral_band)

        self.enforce_diversity = bool(enforce_diversity)
        self.min_each_class = max(0, int(min_each_class))

        # Normalisation des poids
        s = self.rating_weight + self.text_weight + self.noise_weight
        if s <= 0:
            self.rating_weight, self.text_weight, self.noise_weight = 0.55, 0.40, 0.05
            s = 1.0
        self.rating_weight /= s
        self.text_weight /= s
        self.noise_weight /= s

        if seed is not None:
            random.seed(seed)

        if not HAS_TEXTBLOB:
            logger.warning("⚠️ TextBlob non installé. Mode 'Lexicon + Rating' utilisé.")

        # Lexique fallback (simple, mais cohérent)
        self.pos_words = {
            "great": 1.0, "amazing": 1.2, "excellent": 1.2, "good": 0.7, "love": 1.0,
            "perfect": 1.1, "fast": 0.6, "smooth": 0.7, "reliable": 0.8, "recommend": 0.8,
            "value": 0.6, "cheap": 0.3, "solid": 0.5,
        }
        self.neg_words = {
            "bad": -0.8, "worst": -1.2, "broken": -1.1, "slow": -0.7, "overpriced": -0.6,
            "disappointed": -1.0, "terrible": -1.2, "poor": -0.7, "refund": -0.6,
            "issue": -0.5, "problem": -0.6, "late": -0.4,"regret": -1.0,    "avoid": -0.8, 
            "overheats": -0.7,    "stutters": -0.6,   
            "freezes": -0.7,    "drains": -0.6,    "expensive": -0.4,
        }

        # Thèmes pour reviews moins génériques
        self.aspects = {
            "battery": {
                "pos": ["battery lasts all day", "excellent battery life", "great battery"],
                "neu": ["battery is okay", "battery is decent", "battery is average"],
                "neg": ["battery drains fast", "poor battery life", "battery is disappointing"],
            },
            "camera": {
                "pos": ["camera is amazing", "great photos", "excellent camera quality"],
                "neu": ["camera is fine", "camera is okay", "camera is average"],
                "neg": ["camera is disappointing", "photos look noisy", "camera struggles in low light"],
            },
            "performance": {
                "pos": ["very fast", "super smooth", "performance is top-notch"],
                "neu": ["performance is okay", "works fine most of the time", "acceptable speed"],
                "neg": ["lags sometimes", "feels slow", "stutters and freezes"],
            },
            "shipping": {
                "pos": ["shipping was fast", "arrived quickly", "delivery was on time"],
                "neu": ["shipping was acceptable", "arrived as expected", "delivery was okay"],
                "neg": ["shipping was late", "delivery took too long", "packaging was damaged"],
            },
            "value": {
                "pos": ["great value for money", "worth the price", "good deal"],
                "neu": ["price is okay", "fair for what you get", "not bad for the price"],
                "neg": ["too expensive", "overpriced for the features", "not worth the money"],
            },
        }

        self.openers = {
            "pos": ["Love it.", "Very satisfied.", "Great purchase.", "Highly recommended."],
            "neu": ["It's okay.", "Overall it's fine.", "Mixed feelings.", "Decent but not perfect."],
            "neg": ["Disappointed.", "Not happy.", "Would not recommend.", "Regret buying this."],
        }
        
    # src/tools/sentiment_analyzer.py


    def analyze(self, product_name: Optional[str] = None, product: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Alias compatibility method.
        Allows agent to call analyze(product_name=..., product=...),
        while keeping existing analyze_product(product) unchanged.
        """
        if product is None:
            product = {"title": product_name or "Unknown", "rating": 3.0}
        return self.analyze_product(product)

    
    def _extract_key_phrases(self, analyzed_reviews: List[Dict], top_k: int = 3) -> List[str]:
        # Simple: on “force” des thèmes attendus via les aspects
        text = " ".join((r.get("text") or "").lower() for r in analyzed_reviews)

        themes = []
        for k in ["battery", "value", "shipping", "camera", "performance"]:
            if k in text:
                themes.append(k)

        return themes[:top_k] or ["No specific themes detected"]


    def analyze_product(self, product: Dict) -> Dict:
        product_title = product.get("title", "Unknown Product")
        rating = float(product.get("rating", 3.0) or 3.0)

        logger.info(f"🧠 Analyse du sentiment pour : {product_title} (Rating: {rating})")

        reviews, intended_classes = self._simulate_reviews(rating, n=self.n_reviews)

        analyzed_reviews: List[Dict] = []
        dist = {"positive": 0, "neutral": 0, "negative": 0}
        total = 0.0

        for review, intended in zip(reviews, intended_classes):
            score = self._combined_score(text=review, rating=rating)
            label = self._label(score)

            dist[label] += 1
            total += score

            analyzed_reviews.append(
                {
                    "text": review,
                    "score": round(score, 2),
                    "label": label,
                    # garde-le si tu veux débugger; sinon tu peux supprimer
                    "intended": intended,
                }
            )

        avg = total / len(analyzed_reviews) if analyzed_reviews else 0.0
        overall = self._label(avg)

        # NEW: % (utile pour le rapport)
        total_n = max(1, sum(dist.values()))
        dist_pct = {k: round(v / total_n * 100.0, 1) for k, v in dist.items()}

        return {
            # compat ancien schéma
            "average_sentiment": round(avg, 2),
            "sentiment_breakdown": dist,
            "key_phrases": self._extract_key_phrases(analyzed_reviews),

            # détails complets (nouveau schéma)
            "details": {
                "product_id": product.get("id"),
                "average_sentiment_score": round(avg, 2),
                "sentiment_label": overall,
                "sentiment_distribution": dist,
                "sentiment_distribution_pct": dist_pct,
                "analyzed_reviews_sample": analyzed_reviews,
            },
        }


    # ---------- Scoring ----------

    def _combined_score(self, text: str, rating: float) -> float:
        rating_p = self._rating_to_polarity(rating)
        text_p = self._text_polarity(text)
        noise = random.gauss(0, 0.15)


        score = (
            self.rating_weight * rating_p
            + self.text_weight * text_p
            + self.noise_weight * noise
        )

        return max(-1.0, min(1.0, float(score)))

    def _rating_to_polarity(self, rating: float) -> float:
        r = max(1.0, min(5.0, float(rating)))
        return (r - 3.0) / 2.0  # [-1,1]

    def _text_polarity(self, text: str) -> float:
        if HAS_TEXTBLOB:
            try:
                return float(TextBlob(text).sentiment.polarity)
            except Exception:
                return self._lexicon_polarity(text)
        return self._lexicon_polarity(text)

    def _lexicon_polarity(self, text: str) -> float:
        tokens = re.findall(r"[a-zA-Z']+", text.lower())
        if not tokens:
            return 0.0

        negators = {"not", "never", "no", "dont", "don't", "cannot", "can't", "wont", "won't"}
        negate_window = 0

        s = 0.0
        for t in tokens:
            if t in negators:
                negate_window = 2
                continue

            w = 0.0
            if t in self.pos_words:
                w = self.pos_words[t]
            elif t in self.neg_words:
                w = self.neg_words[t]

            if negate_window > 0 and w != 0.0:
                w = -w
                negate_window -= 1
            elif negate_window > 0:
                negate_window -= 1

            s += w

        return math.tanh(s / 2.0)


        s = 0.0
        for t in tokens:
            if t in self.pos_words:
                s += self.pos_words[t]
            elif t in self.neg_words:
                s += self.neg_words[t]

        return math.tanh(s / 2.0)

    def _label(self, score: float) -> str:
        if score >= self.neutral_band:
            return "positive"
        if score <= -self.neutral_band:
            return "negative"
        return "neutral"

    # ---------- Simulation avis ----------

    def _simulate_reviews(self, rating: float, n: int) -> Tuple[List[str], List[str]]:
        rating = max(1.0, min(5.0, float(rating)))
        probs = self._class_probs_from_rating(rating)

        classes = [self._sample_class(probs) for _ in range(int(n))]

        # NEW: forcer une diversité minimale (évite "je ne vois que neutral")
        if self.enforce_diversity and self.min_each_class > 0:
            classes = self._enforce_minimum_diversity(classes, probs, min_each=self.min_each_class)

        reviews = [self._build_review(c) for c in classes]
        return reviews, classes

    def _class_probs_from_rating(self, rating: float) -> Dict[str, float]:
        # Probabilités "raisonnables"
        if rating >= 4.6:
            return {"positive": 0.78, "neutral": 0.17, "negative": 0.05}
        if rating >= 4.2:
            return {"positive": 0.68, "neutral": 0.22, "negative": 0.10}
        if rating >= 3.8:
            return {"positive": 0.55, "neutral": 0.28, "negative": 0.17}
        if rating >= 3.2:
            return {"positive": 0.38, "neutral": 0.34, "negative": 0.28}
        if rating >= 2.6:
            return {"positive": 0.25, "neutral": 0.30, "negative": 0.45}
        return {"positive": 0.12, "neutral": 0.18, "negative": 0.70}

    def _sample_class(self, probs: Dict[str, float]) -> str:
        r = random.random()
        if r < probs["positive"]:
            return "positive"
        if r < probs["positive"] + probs["neutral"]:
            return "neutral"
        return "negative"

    def _enforce_minimum_diversity(
        self, classes: List[str], probs: Dict[str, float], min_each: int = 1
    ) -> List[str]:
        """
        Assure au moins 'min_each' occurrences de chaque classe (si possible),
        en faisant des swaps minimalement intrusifs.
        """
        n = len(classes)
        if n <= 0:
            return classes

        targets = ["positive", "neutral", "negative"]
        counts = {k: classes.count(k) for k in targets}

        # si trop petit pour satisfaire min_each pour les 3 classes, on n'insiste pas
        if n < 3 * min_each:
            return classes

        # On remplace des classes "surreprésentées" par celles manquantes,
        # en suivant le rating via probs (on évite de faire 5 négatifs sur un rating 4.9)
        for needed in targets:
            while counts[needed] < min_each:
                # choisir une classe à réduire: celle avec le plus grand excès vs prob attendu
                reducible = sorted(
                    targets,
                    key=lambda k: (counts[k] - probs[k] * n),
                    reverse=True,
                )
                donor = next((k for k in reducible if k != needed and counts[k] > min_each), None)
                if donor is None:
                    break

                # remplacer un index donor par needed
                donor_idxs = [i for i, c in enumerate(classes) if c == donor]
                if not donor_idxs:
                    break
                idx = random.choice(donor_idxs)
                classes[idx] = needed
                counts[donor] -= 1
                counts[needed] += 1

        return classes

    def _build_review(self, cls: str) -> str:
        aspect_keys = random.sample(list(self.aspects.keys()), k=random.choice([2, 3]))

        if cls == "positive":
            opener = random.choice(self.openers["pos"])
            bits = [random.choice(self.aspects[k]["pos"]) for k in aspect_keys]
            tail = random.choice(["Would buy again.", "Really impressed.", "No complaints."])
        elif cls == "neutral":
            opener = random.choice(self.openers["neu"])
            bits = [random.choice(self.aspects[k]["neu"]) for k in aspect_keys]
            tail = random.choice(["It's fine overall.", "Could be better.", "Meets expectations."])
        else:
            opener = random.choice(self.openers["neg"])
            bits = [random.choice(self.aspects[k]["neg"]) for k in aspect_keys]
            tail = random.choice(["Not worth it.", "Needs improvement.", "Would avoid."])

        # Ajoute des mots compatibles lexique (fallback)
        if cls == "positive" and random.random() < 0.60:
            bits.append(random.choice(["great", "excellent", "amazing", "good value"]))
        if cls == "negative" and random.random() < 0.60:
            bits.append(random.choice(["bad", "terrible", "overpriced", "disappointed"]))

        return f"{opener} " + ", ".join(bits) + f". {tail}"


if __name__ == "__main__":
    analyzer = SentimentAnalyzer(seed=42, n_reviews=18, enforce_diversity=True, min_each_class=1)
    fake_product = {"id": "test_1", "title": "Super iPhone", "rating": 4.8}
    print(analyzer.analyze_product(fake_product))
