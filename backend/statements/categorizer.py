"""Transaction categorization utilities.

Provides a small rule-based classifier plus optional fallbacks:
- External HTTP categorizer wrapper (can point at Plaid/Yodlee proxies).
- Zero-shot LLM fallback (only if configured with an API key).

Nothing is enabled by default; `build_categorizer_from_env()` inspects env
flags to decide whether to return a pipeline. See docs at bottom of file.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Mapping, Optional

# Core categories shared by the built-in rules. Feel free to extend.
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "income",
    "salary",
    "bonus",
    "groceries",
    "dining",
    "fuel",
    "travel",
    "health",
    "utilities",
    "shopping",
    "entertainment",
    "housing",
    "transfer",
    "fees",
    "other",
)

# Lightweight keyword map for rule-based classification.
DEFAULT_KEYWORD_MAP: Dict[str, tuple[str, ...]] = {
    "income": ("payroll", "deposit", "paycheck", "employer", "ach credit"),
    "salary": ("salary", "w2", "direct deposit"),
    "bonus": ("bonus", "stock grant", "rsu", "equity"),
    "groceries": ("grocery", "market", "supermarket", "walmart", "target", "trader joe", "aldi", "whole foods"),
    "dining": ("restaurant", "grill", "pizza", "burger", "bistro", "cafe", "coffee", "starbucks", "dunkin"),
    "fuel": ("gas", "fuel", "shell", "chevron", "exxon", "petro", "bp station"),
    "travel": ("airlines", "hotel", "marriott", "hilton", "airbnb", "uber", "lyft", "delta", "united", "aa "),
    "health": ("pharmacy", "clinic", "hospital", "dental", "vision", "hsa", "health"),
    "utilities": ("electric", "power", "water", "utility", "internet", "comcast", "xfinity", "verizon", "att", "t-mobile"),
    "shopping": ("amazon", "best buy", "electronics", "retail", "mall"),
    "entertainment": ("netflix", "spotify", "hulu", "disney", "amc", "cinema", "theatre", "concert"),
    "housing": ("rent", "mortgage", "landlord", "hoa"),
    "transfer": ("transfer", "zelle", "venmo", "cash app", "reimbursement"),
    "fees": ("fee", "interest charge", "late fee", "overdraft"),
}

# Default merchant/category mapping for exact/contains matches.
DEFAULT_MERCHANT_MAP: Dict[str, str] = {
    "walmart": "groceries",
    "target": "groceries",
    "trader joe's": "groceries",
    "whole foods": "groceries",
    "costco": "groceries",
    "amazon": "shopping",
    "starbucks": "dining",
    "mcdonald's": "dining",
    "shell": "fuel",
    "chevron": "fuel",
    "exxon": "fuel",
    "hilton": "travel",
    "marriott": "travel",
    "airbnb": "travel",
    "uber": "travel",
    "lyft": "travel",
    "netflix": "entertainment",
    "spotify": "entertainment",
    "verizon": "utilities",
    "comcast": "utilities",
    "xfinity": "utilities",
}


def _normalize(text: str | None) -> str:
    """Lowercases and collapses whitespace for matching."""
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


@dataclass
class CategorizationResult:
    category: str
    confidence: float
    source: str
    merchant: str | None = None
    notes: str | None = None


class RuleBasedCategorizer:
    """Simple keyword/merchant classifier.

    Parameters:
        keyword_map: mapping of category -> keywords/phrases
        merchant_map: mapping of merchant string -> category
        min_confidence: minimum confidence to emit a result
    """

    def __init__(
        self,
        keyword_map: Mapping[str, Iterable[str]] | None = None,
        merchant_map: Mapping[str, str] | None = None,
        min_confidence: float = 0.35,
        default_category: str = "other",
    ) -> None:
        self.keyword_map: Dict[str, tuple[str, ...]] = {
            k.lower(): tuple(v) for k, v in (keyword_map or DEFAULT_KEYWORD_MAP).items()
        }
        self.merchant_map: Dict[str, str] = {k.lower(): v.lower() for k, v in (merchant_map or DEFAULT_MERCHANT_MAP).items()}
        self.min_confidence = min_confidence
        self.default_category = default_category

    def _score_keywords(self, text: str, keywords: Iterable[str]) -> float:
        hits = 0
        for kw in keywords:
            kw_norm = _normalize(kw)
            if kw_norm and kw_norm in text:
                hits += 1
        if hits == 0:
            return 0.0
        # Scale with diminishing returns; cap at 1.0
        return min(1.0, 0.4 + 0.2 * hits)

    def categorize(
        self,
        description: str,
        amount: float,
        merchant: str | None = None,
        mcc: str | None = None,
    ) -> CategorizationResult | None:
        text = _normalize(description)
        merchant_norm = _normalize(merchant)

        # Merchant map exact/contains match
        if merchant_norm:
            if merchant_norm in self.merchant_map:
                cat = self.merchant_map[merchant_norm]
                return CategorizationResult(category=cat, confidence=0.9, source="rules-merchant", merchant=merchant_norm)
            # fallback: contains any merchant key
            for key, cat in self.merchant_map.items():
                if key in merchant_norm:
                    return CategorizationResult(category=cat, confidence=0.75, source="rules-merchant", merchant=merchant_norm)

        # Keyword scoring
        best_cat = None
        best_score = 0.0
        for cat, keywords in self.keyword_map.items():
            score = self._score_keywords(text, keywords)
            # Slight preference for positive amounts mapping to income-ish categories
            if amount > 0 and cat in ("income", "salary", "bonus"):
                score += 0.1
            if score > best_score:
                best_score = score
                best_cat = cat

        if best_cat and best_score >= self.min_confidence:
            return CategorizationResult(category=best_cat, confidence=min(best_score, 1.0), source="rules", merchant=merchant_norm or None)

        return CategorizationResult(category=self.default_category, confidence=0.0, source="rules-fallback", merchant=merchant_norm or None)


class ExternalAPICategorizer:
    """Thin HTTP wrapper for third-party categorizers (Plaid/Yodlee proxies, etc.).

    Expects a JSON POST endpoint that accepts: description, amount, merchant, mcc
    and responds with: {"category": "...", "confidence": 0.82, "merchant": "..."}.
    """

    def __init__(self, name: str, url: str, api_key: str | None = None, timeout: float = 5.0) -> None:
        self.name = name
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def categorize(
        self,
        description: str,
        amount: float,
        merchant: str | None = None,
        mcc: str | None = None,
    ) -> CategorizationResult | None:
        payload = {
            "description": description,
            "amount": amount,
            "merchant": merchant,
            "mcc": mcc,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
        except (urllib.error.URLError, ValueError, json.JSONDecodeError):
            return None

        category = _normalize(parsed.get("category"))
        if not category:
            return None
        confidence = float(parsed.get("confidence") or 0.5)
        merchant_resp = parsed.get("merchant") or merchant
        return CategorizationResult(category=category, confidence=confidence, source=self.name, merchant=_normalize(merchant_resp) or None)


class ZeroShotLLMCategorizer:
    """Optional zero-shot LLM classifier. Requires OPENAI_API_KEY or STATEMENT_LLM_API_KEY."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        categories: Iterable[str] | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.api_key = api_key or os.getenv("STATEMENT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.categories = list(categories or DEFAULT_CATEGORIES)
        self.temperature = temperature

    def categorize(
        self,
        description: str,
        amount: float,
        merchant: str | None = None,
        mcc: str | None = None,
    ) -> CategorizationResult | None:
        if not self.api_key:
            raise RuntimeError("LLM categorizer enabled but no STATEMENT_LLM_API_KEY/OPENAI_API_KEY provided.")

        # Lazy import so environments without openai installed don't break.
        client = None
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Categorize the transaction into one of: {', '.join(self.categories)}. Return only the category.",
                    },
                    {
                        "role": "user",
                        "content": f"Description: {description}\nAmount: {amount}\nMerchant: {merchant or ''}\nMCC: {mcc or ''}",
                    },
                ],
                max_tokens=8,
                temperature=self.temperature,
            )
            raw = response.choices[0].message.content or ""
        except ImportError as exc:
            # Try legacy openai import if available
            try:
                import openai  # type: ignore

                openai.api_key = self.api_key
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": f"Categorize the transaction into one of: {', '.join(self.categories)}. Return only the category.",
                        },
                        {
                            "role": "user",
                            "content": f"Description: {description}\nAmount: {amount}\nMerchant: {merchant or ''}\nMCC: {mcc or ''}",
                        },
                    ],
                    max_tokens=8,
                    temperature=self.temperature,
                )
                raw = response["choices"][0]["message"]["content"] or ""
            except ImportError as exc2:
                raise RuntimeError("Install `openai` to use the LLM categorizer.") from exc2
            except Exception as exc2:
                raise RuntimeError(f"LLM categorizer call failed: {exc2}") from exc2
        except Exception as exc:
            raise RuntimeError(f"LLM categorizer call failed: {exc}") from exc

        category = _normalize(raw.splitlines()[0] if raw else "")
        if not category:
            return None
        return CategorizationResult(category=category, confidence=0.5, source="llm", merchant=_normalize(merchant) or None)


class CategorizerPipeline:
    """Pipeline that chains rule-based classification with an optional fallback."""

    def __init__(
        self,
        primary: RuleBasedCategorizer,
        fallback: Optional[Callable[[str, float, str | None, str | None], CategorizationResult | None]] = None,
        min_confidence_for_rules: float = 0.6,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.min_confidence_for_rules = min_confidence_for_rules

    def categorize(
        self,
        description: str,
        amount: float,
        merchant: str | None = None,
        mcc: str | None = None,
    ) -> CategorizationResult | None:
        result = self.primary.categorize(description, amount, merchant=merchant, mcc=mcc)
        if result and result.confidence >= self.min_confidence_for_rules:
            return result

        if self.fallback:
            fb = self.fallback(description, amount, merchant, mcc)
            if fb:
                return fb
        return result


def _load_json_mapping(path: str) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        # Normalize keys/values
        return {str(k).lower(): str(v).lower() for k, v in data.items() if k and v}
    except (OSError, json.JSONDecodeError):
        return {}


def build_categorizer_from_env() -> CategorizerPipeline | None:
    """Creates a pipeline based on env flags.

    Env vars:
      STATEMENT_CATEGORIZER_ENABLED=1      -> turn on auto-categorization
      STATEMENT_MERCHANT_MAP=<path.json>   -> optional merchant->category map
      STATEMENT_EXTERNAL_URL=<https://...> -> optional HTTP fallback (Plaid/Yodlee proxy)
      STATEMENT_EXTERNAL_TOKEN=<token>     -> optional bearer token for HTTP fallback
      STATEMENT_LLM_ENABLE=1               -> enable LLM fallback (requires API key)
      STATEMENT_LLM_MODEL=<model>          -> override model name
      STATEMENT_RULE_CONFIDENCE=0.6        -> rule confidence threshold before fallback
    """

    if str(os.getenv("STATEMENT_CATEGORIZER_ENABLED", "")).lower() not in {"1", "true", "yes", "on"}:
        return None

    merchant_map_path = os.getenv("STATEMENT_MERCHANT_MAP", "")
    merchant_map = DEFAULT_MERCHANT_MAP | _load_json_mapping(merchant_map_path)
    rule = RuleBasedCategorizer(merchant_map=merchant_map)

    rule_confidence = float(os.getenv("STATEMENT_RULE_CONFIDENCE", 0.6))
    fallback_callable: Optional[Callable[[str, float, str | None, str | None], CategorizationResult | None]] = None

    external_url = os.getenv("STATEMENT_EXTERNAL_URL")
    if external_url:
        external_token = os.getenv("STATEMENT_EXTERNAL_TOKEN")
        external_name = os.getenv("STATEMENT_EXTERNAL_NAME", "external")
        external = ExternalAPICategorizer(external_name, external_url, api_key=external_token)
        fallback_callable = external.categorize

    if not fallback_callable and str(os.getenv("STATEMENT_LLM_ENABLE", "")).lower() in {"1", "true", "yes", "on"}:
        llm = ZeroShotLLMCategorizer(
            api_key=os.getenv("STATEMENT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            model=os.getenv("STATEMENT_LLM_MODEL", "gpt-4o-mini"),
        )
        fallback_callable = llm.categorize

    return CategorizerPipeline(primary=rule, fallback=fallback_callable, min_confidence_for_rules=rule_confidence)


# Notes for users:
# - By default only the rule-based categorizer runs.
# - To try a Plaid/Yodlee proxy, point STATEMENT_EXTERNAL_URL to your service that
#   accepts (description, amount, merchant, mcc) and returns a category.
# - To use an OpenAI-compatible LLM, set STATEMENT_LLM_ENABLE=1 and provide an API key.
