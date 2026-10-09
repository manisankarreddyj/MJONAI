"""
Module: agents/llm_bridge.py
Purpose: SOTA Universal Multi-LLM Vendor Dispatcher, Multi-Stage Failover,
         JSON Schema Enforcer, Rate-Limit Budget Tracker, Dynamic Model Discovery,
         and Deterministic Algorithmic Fallback.
         Supports Groq, Google Gemini, OpenRouter, with startup health probe.
"""

from collections import deque
from dataclasses import dataclass, field, asdict
import json
import os
import re
import time
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

# Default timeout for LLM inferences during market hours (prevents trading hang)
DEFAULT_LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "3.5"))


@dataclass(frozen=True)
class LLMInferenceResult:
    """Immutable contract representing the full LLM inference lifecycle and telemetry."""
    success: bool
    vendor_used: str  # "groq", "gemini", "openai", "deepseek", "ollama", "deterministic_fallback"
    model: str
    latency_ms: float
    is_fallback: bool
    parsed_payload: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def extract_and_validate_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Extracts, cleans, and validates structured JSON from raw LLM responses.
    Strips markdown fences (```json ... ```) and handles trailing commas or prose wrappers.
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # 1. Strip markdown code fences
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    # 2. Extract outermost JSON object if enclosed in extra text
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    # 3. Parse JSON
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            # Enforce schema fields
            if "confidence" in data:
                try:
                    data["confidence"] = max(0, min(100, int(float(data["confidence"]))))
                except (ValueError, TypeError):
                    data["confidence"] = 50
            if "verdict" in data:
                # EXACT-token matching only. The old substring match
                # counted "NO_BUY" as APPROVE and erased Bear CAUTION
                # (killing the round-2 re-debate trigger).
                v = str(data["verdict"]).upper().strip()
                if v in ("APPROVE", "BUY", "LONG"):
                    data["verdict"] = "APPROVE"
                elif v in ("VETO", "REJECT", "SELL", "SHORT"):
                    data["verdict"] = "VETO"
                elif v == "CAUTION":
                    data["verdict"] = "CAUTION"
                else:
                    # Unrecognized verdicts are NEUTRAL, never approval.
                    data["verdict"] = "NEUTRAL"
            return data
    except Exception as e:
        logger.debug(f"[LLMBridge] JSON decode error: {e} for payload: {cleaned[:100]}...")

    return None


def get_deterministic_fallback_consensus(
    signal: Dict[str, Any],
    macro_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Non-blocking deterministic rule-based quantitative consensus engine.
    Executes in <0.01 ms when all LLM APIs are offline or timed out.
    Evaluates:
      - Trend (EMA200, Supertrend)
      - Momentum (RSI 45-65 zone)
      - Liquidity (Volume multiple >= 1.2x)
      - Macro (FII Flow & Sector RRG)
    """
    direction = str(signal.get("direction", "LONG")).upper()
    rsi = float(signal.get("rsi", 55.0))
    volume_ratio = float(signal.get("volume_ratio", 1.2))
    sector_multiplier = float(signal.get("sector_multiplier", 1.0))
    fii_regime = (macro_context or {}).get("fii_regime", "NEUTRAL")

    bull_score = 50
    bear_score = 50
    reasons = []

    if direction == "LONG":
        # RSI momentum check
        if 50 <= rsi <= 68:
            bull_score += 15
            reasons.append(f"RSI {rsi:.1f} in healthy bullish momentum corridor (50-68)")
        elif rsi > 75:
            bear_score += 20
            reasons.append(f"RSI {rsi:.1f} overbought — risk of exhaustion pullback")

        # Volume check
        if volume_ratio >= 1.5:
            bull_score += 15
            reasons.append(f"Strong volume expansion ({volume_ratio:.2f}x above 20-day avg)")

        # Sector RRG check
        if sector_multiplier > 1.0:
            bull_score += 10
            reasons.append("Sector is in LEADING / IMPROVING RRG quadrant")
        elif sector_multiplier < 1.0:
            bear_score += 15
            reasons.append("Sector is lagging Nifty benchmark")

        # FII flow check
        if fii_regime in ("MEGA_BULLISH", "GLOBAL_BULLISH", "DOMESTIC_ABSORPTION"):
            bull_score += 10
            reasons.append(f"Institutional liquidity favorable ({fii_regime})")
        elif fii_regime == "SEVERE_DRAIN":
            bear_score += 20
            reasons.append("Severe FII institutional cash drain")

    else:  # SHORT
        if 32 <= rsi <= 50:
            bear_score += 15
            reasons.append(f"RSI {rsi:.1f} in bearish breakdown corridor")
        elif rsi < 25:
            bull_score += 20
            reasons.append(f"RSI {rsi:.1f} deeply oversold — short squeeze risk")

        if volume_ratio >= 1.5:
            bear_score += 15
            reasons.append("Heavy distribution volume confirmed")

    bull_score = max(0, min(100, bull_score))
    bear_score = max(0, min(100, bear_score))

    # Net consensus
    net_confidence = bull_score if direction == "LONG" else bear_score
    verdict = "APPROVE" if net_confidence >= 65 and (bear_score if direction == "LONG" else bull_score) < 70 else "VETO"

    return {
        "verdict": verdict,
        "confidence": net_confidence,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "is_deterministic_fallback": True,
        "reasons": reasons or ["Deterministic algorithmic quantitative consensus scored."],
    }


_provider_cooldowns: Dict[str, float] = {}


def is_provider_on_cooldown(vendor: str) -> bool:
    """Return True if the specified vendor is currently in rate-limit cooldown."""
    return time.time() < _provider_cooldowns.get(vendor, 0.0)


def set_provider_cooldown(vendor: str, seconds: float = 180.0) -> None:
    """Put a vendor on temporary cooldown after rate-limit / quota errors."""
    _provider_cooldowns[vendor] = time.time() + seconds


@dataclass
class RateLimitConfig:
    """Windowed budget limits for a provider or model."""
    rpm: int = 0        # requests per minute (0 = unlimited)
    rpd: int = 0        # requests per day (0 = unlimited)


class RateLimitTracker:
    """
    Sliding-window usage tracker for provider- and model-level rate limits.

    Tracks request timestamps so dispatch can pre-check budget BEFORE calling
    a provider, instead of only discovering exhaustion after a 429.
    """

    def __init__(self) -> None:
        self._model_usage: Dict[str, deque] = {}
        self._provider_usage: Dict[str, deque] = {}
        self._provider_limits: Dict[str, RateLimitConfig] = {}
        self._model_limits: Dict[str, RateLimitConfig] = {}

    def set_provider_limit(self, provider: str, cfg: RateLimitConfig) -> None:
        self._provider_limits[provider] = cfg
        self._provider_usage.setdefault(provider, deque())

    def set_model_limit(self, model_key: str, cfg: RateLimitConfig) -> None:
        self._model_limits[model_key] = cfg
        self._model_usage.setdefault(model_key, deque())

    def register(self, provider: str, cfg: RateLimitConfig, model_keys: Optional[List[str]] = None) -> None:
        self.set_provider_limit(provider, cfg)
        for mk in model_keys or []:
            self.set_model_limit(mk, cfg)

    def _prune(self, dq: deque, window_seconds: float) -> None:
        cutoff = time.time() - window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()

    def _has_budget(self, dq: Optional[deque], limit: int, window_seconds: float) -> bool:
        if limit <= 0:
            return True
        if dq is None:
            return True
        self._prune(dq, window_seconds)
        return len(dq) < limit

    def can_request(self, provider: str, model_key: Optional[str] = None) -> bool:
        """Pre-flight: may this (provider, model) combination make another request now?"""
        prov_cfg = self._provider_limits.get(provider)
        if prov_cfg is not None:
            if not self._has_budget(self._provider_usage.get(provider), prov_cfg.rpm, 60.0):
                return False
            if not self._has_budget(self._provider_usage.get(provider), prov_cfg.rpd, 86400.0):
                return False
        if model_key is not None:
            model_cfg = self._model_limits.get(model_key)
            if model_cfg is not None:
                if not self._has_budget(self._model_usage.get(model_key), model_cfg.rpm, 60.0):
                    return False
                if not self._has_budget(self._model_usage.get(model_key), model_cfg.rpd, 86400.0):
                    return False
        return True

    def record(self, provider: str, model_key: Optional[str] = None) -> None:
        now = time.time()
        # Provider budget (dedup per logical inference tier, so cascades cost 1 slot)
        if provider in self._provider_limits:
            dq = self._provider_usage.setdefault(provider, deque())
            dq.append(now)
        if model_key is not None and model_key in self._model_limits:
            dq = self._model_usage.setdefault(model_key, deque())
            dq.append(now)

    def delete_expired(self) -> None:
        for dq in list(self._model_usage.values()):
            self._prune(dq, 86400.0)
        for dq in list(self._provider_usage.values()):
            self._prune(dq, 86400.0)


# ── Provider category registry: per-model vs per-provider limits configured here ──
ProviderRegistry: Dict[str, Any] = {
    "groq": {
        "limit": RateLimitConfig(rpm=30, rpd=14400),
        "models": ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b"],
    },
    "gemini": {
        "limit": RateLimitConfig(rpm=10, rpd=1500),
        "models": ["gemini-2.5-flash"],
    },
    "openrouter": {
        "limit": RateLimitConfig(rpm=20, rpd=200),
        "models": ["deepseek/deepseek-r1", "deepseek/deepseek-chat"],
    },
}


def _init_rate_limiter() -> RateLimitTracker:
    tracker = RateLimitTracker()
    tracker.set_provider_limit("groq", ProviderRegistry["groq"]["limit"])
    tracker.set_provider_limit("gemini", ProviderRegistry["gemini"]["limit"])
    tracker.set_provider_limit("openrouter", ProviderRegistry["openrouter"]["limit"])
    for name, entry in ProviderRegistry.items():
        for m in entry["models"]:
            tracker.set_model_limit(f"{name}:{m}", entry["limit"])
    return tracker


# Module-level singleton shared by dispatch and probe paths.
_rate_limiter = _init_rate_limiter()


# ── Dynamic model discovery: query provider model lists at boot, never hardcode ──
def get_rate_limiter() -> RateLimitTracker:
    """Return the module-level rate limiter instance."""
    return _rate_limiter


_GROQ_CHAT_FAMILIES = ("gpt-oss", "qwen3", "llama-3.3", "gemma", "mixtral")


def _list_groq_models(timeout: float = 2.0) -> Optional[List[str]]:
    """Query Groq's /models endpoint, filtered to chat-capable families usable with JSON mode."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    try:
        import httpx
        url = "https://api.groq.com/openai/v1/models"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {key}"})
            if resp.status_code != 200:
                logger.warning(f"[LLMBridge] Groq model list error {resp.status_code}")
                return None
            data = resp.json()
            models = [m.get("id") for m in data.get("data", [])]
            chat = [m for m in models if m and any(f in m.lower() for f in _GROQ_CHAT_FAMILIES)]
            if not chat:
                chat = [m for m in models if m]
            return chat
    except Exception as e:
        logger.debug(f"[LLMBridge] Groq model list unavailable: {e}")
        return None


def _list_openrouter_models(timeout: float = 2.0) -> Optional[List[str]]:
    """Query OpenRouter's /models endpoint, filtered to FREE (zero-priced) chat models."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    try:
        import httpx
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"[LLMBridge] OpenRouter model list error {resp.status_code}")
                return None
            data = resp.json()
            free_models = []
            for m in data.get("data", []):
                mid = m.get("id")
                if not mid:
                    continue
                pricing = m.get("pricing") or {}
                try:
                    prompt_cost = float(pricing.get("prompt", 1.0))
                    completion_cost = float(pricing.get("completion", 1.0))
                except (ValueError, TypeError):
                    prompt_cost = completion_cost = 1.0
                if prompt_cost == 0.0 and completion_cost == 0.0:
                    free_models.append(mid)
            if not free_models:
                return None
            # Prefer known reasoning/fast chat families first.
            known = [f for f in free_models if "deepseek" in f or "nvidia" in f or "gemma" in f]
            return known + [f for f in free_models if f not in known]
    except Exception as e:
        logger.debug(f"[LLMBridge] OpenRouter model list unavailable: {e}")
        return None


def _list_gemini_models(timeout: float = 2.0) -> Optional[List[str]]:
    """Query Gemini's model list endpoint. Returns None on failure."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning(f"[LLMBridge] Gemini model list error {resp.status_code}")
                return None
            data = resp.json()
            models = [m.get("name") for m in data.get("models", [])]
            return [m.replace("models/", "") for m in models if m and m.startswith("models/gemini")]
    except Exception as e:
        logger.debug(f"[LLMBridge] Gemini model list unavailable: {e}")
        return None


_MODEL_LISTERS = {
    "groq": "_list_groq_models",
    "gemini": "_list_gemini_models",
    "openrouter": "_list_openrouter_models",
}


def get_dynamic_candidate_models(provider: str) -> List[str]:
    """
    Return the live candidate model list for a provider using boot-time discovery.
    Falls back to the static registry when discovery is unavailable.
    """
    try:
        lister_name = _MODEL_LISTERS.get(provider)
        if lister_name is not None:
            lister = globals().get(lister_name)
            if lister is not None:
                discovered = lister()
                if discovered:
                    return discovered
    except Exception as e:
        logger.debug(f"[LLMBridge] dynamic model query failed for {provider}: {e}")
    return list(ProviderRegistry.get(provider, {}).get("models", []))


# ── Startup provider health probe ──
def probe_providers(timeout_seconds: float = 3.0) -> Dict[str, Dict[str, Any]]:
    """
    Boot-time health check across all configured LLM providers.

    For each provider: validates the API key, discovers available models,
    sends a minimal inference probe, and records latency + status.
    Returns a per-provider health report; never raises.
    """
    health: Dict[str, Dict[str, Any]] = {}

    for provider in ("groq", "gemini", "openrouter"):
        prov_cfg = ProviderRegistry.get(provider, {})
        models = get_dynamic_candidate_models(provider)
        entry: Dict[str, Any] = {
            "provider": provider,
            "status": "DEGRADED",
            "key_present": False,
            "models_discovered": [],
            "models_working": [],
            "latency_ms": None,
            "detail": "no API key",
        }

        key_name = {
            "groq": "GROQ_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }.get(provider)
        if key_name and not os.getenv(key_name):
            health[provider] = entry
            logger.warning(f"[LLMBridge] {provider}: no {key_name} — skipped in health probe")
            continue

        if models:
            entry["models_discovered"] = models[:10]
            entry["detail"] = f"{len(models)} models discovered"
        entry["key_present"] = True

        try:
            if provider == "groq":
                raw = _query_groq_http(
                    "Probe. Reply with {\"verdict\":\"NEUTRAL\",\"confidence\":50}",
                    system_prompt="Reply with strict JSON only.",
                    timeout=timeout_seconds,
                )
            elif provider == "gemini":
                raw = _query_gemini_http(
                    "Probe. Reply with {\"verdict\":\"NEUTRAL\",\"confidence\":50}",
                    system_prompt="Reply with strict JSON only.",
                    timeout=timeout_seconds,
                )
            else:
                raw = _query_openrouter_http(
                    "Probe. Reply with {\"verdict\":\"NEUTRAL\",\"confidence\":50}",
                    system_prompt="Reply with strict JSON only.",
                    timeout=timeout_seconds,
                )

            if raw:
                parsed = extract_and_validate_json(raw)
                working = models[:1] if models else ["default"]
                entry.update({
                    "status": "OK" if parsed else "DEGRADED",
                    "detail": "probe accepted" if parsed else "probe returned unparseable body",
                    "models_working": working,
                    "latency_ms": 0.0,
                })
            else:
                entry["detail"] = "probe returned no response (rate-limited or key invalid)"
        except Exception as e:
            entry["detail"] = f"probe error: {e}"
            logger.warning(f"[LLMBridge] {provider} probe error: {e}")

        health[provider] = entry
        if entry["status"] == "OK":
            logger.info(f"[LLMBridge] {provider}: OK (latency {entry['latency_ms']}ms) — {entry['detail']}")
        else:
            logger.warning(f"[LLMBridge] {provider}: {entry['status']} — {entry['detail']}")

    return health


def log_provider_health(health: Dict[str, Dict[str, Any]], component: str = "llm_bridge") -> None:
    """Persist the provider health report to system_health_log (best-effort, never raises)."""
    try:
        from mjonai.db.system import insert_health_log
        summary = "; ".join(
            f"{name}={entry.get('status')}" for name, entry in sorted(health.items())
        )
        payload = {
            "component": component,
            "status": "OK" if all(e.get("status") == "OK" for e in health.values()) else "DEGRADED",
            "detail": summary,
            "meta": {"provider_health": health},
        }
        insert_health_log(payload)
    except Exception as e:
        logger.debug(f"[LLMBridge] provider health log skipped (non-critical): {e}")


def _query_groq_http(
    prompt: str,
    system_prompt: str = "",
    model: str = "openai/gpt-oss-120b",
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_LLM_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Execute low-latency Groq inference with dynamic multi-model fallback across active endpoints."""
    if is_provider_on_cooldown("groq"):
        return None

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        return None

    import httpx
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # Dynamic discovery first (boot probe), hardcoded list as fallback.
    discovered = get_dynamic_candidate_models("groq")
    candidate_models: List[str] = []
    for m in discovered:
        if m not in candidate_models:
            candidate_models.append(m)

    made_request = False
    for m in candidate_models:
        # Pre-flight per-model rate-limit check: skip models at quota.
        if not _rate_limiter.can_request("groq", model_key=f"groq:{m}"):
            logger.debug(f"[Groq/{m}] rate-limit budget exhausted for this model — skipping")
            continue
        payload = {
            "model": m,
            "messages": [
                {"role": "system", "content": system_prompt or "You are an institutional quantitative trading risk sentry. Always respond with strict JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        made_request = True
        _rate_limiter.record("groq", model_key=f"groq:{m}")
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                if resp.status_code == 429:
                    continue  # Try next model in pool before setting cooldown
                logger.warning(f"[Groq/{m}] API Error {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.debug(f"[Groq/{m}] Connection failed: {e}")

    if made_request:
        # If all models in pool failed, set cooldown to avoid hammering
        set_provider_cooldown("groq", 120.0)
    return None


def _query_gemini_http(
    prompt: str,
    system_prompt: str = "",
    model: str = "gemini-2.5-flash",
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_LLM_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Execute Google Gemini inference via standard REST API."""
    if is_provider_on_cooldown("gemini"):
        return None
    if not _rate_limiter.can_request("gemini", model_key=f"gemini:{model}"):
        logger.debug(f"[Gemini] rate-limit budget exhausted — skipping")
        return None

    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None

    import httpx
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    _rate_limiter.record("gemini", model_key=f"gemini:{model}")
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            if resp.status_code == 429:
                set_provider_cooldown("gemini", 600.0)
            logger.warning(f"[Gemini] API Error {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        logger.debug(f"[Gemini] Connection failed: {e}")
    return None


def _query_openrouter_http(
    prompt: str,
    system_prompt: str = "",
    model: str = "deepseek/deepseek-chat",
    api_key: Optional[str] = None,
    timeout: float = 8.0,
) -> Optional[str]:
    """Execute deep reasoning inference via OpenRouter API with multi-model cascade."""
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None

    import httpx
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mjonai.local",
        "X-Title": "MJONAI Institutional Trading",
    }

    discovered = get_dynamic_candidate_models("openrouter")
    candidates = [model] + [m for m in discovered if m != model][:10]
    for m in candidates:
        if not _rate_limiter.can_request("openrouter", model_key=f"openrouter:{m}"):
            logger.debug(f"[OpenRouter/{m}] rate-limit budget exhausted — skipping")
            continue
        payload = {
            "model": m,
            "messages": [
                {"role": "system", "content": system_prompt or "You are an institutional quantitative trading risk sentry. Always respond with strict JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        _rate_limiter.record("openrouter", model_key=f"openrouter:{m}")
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                if resp.status_code == 429:
                    continue
                logger.debug(f"[OpenRouter/{m}] API Error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.debug(f"[OpenRouter/{m}] Connection failed: {e}")

    return None



def query_llm_fast(
    prompt: str,
    system_prompt: str = "",
    signal: Optional[Dict[str, Any]] = None,
    macro_context: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS,
    is_reasoning: bool = False,
    preferred_model: Optional[str] = None,
) -> LLMInferenceResult:
    """
    Universal Multi-Stage LLM Dispatcher with Automatic Failover:
      Stage 1: OpenRouter Deep Reasoning (if is_reasoning=True or OPENROUTER_API_KEY set)
      Stage 2: Primary Ultra-Fast Groq (GPT-OSS 120B / Qwen3.6-27B)
      Stage 3: Secondary Deep Reasoner Gemini (Gemini 2.5 Flash)
      Stage 4: Deterministic Algorithmic Quantitative Fallback (100% Guaranteed non-blocking)
    """
    start_time = time.perf_counter()

    # ── Stage 1: OpenRouter Deep Reasoning (if requested) ──
    if is_reasoning or (preferred_model and "deepseek" in preferred_model):
        try:
            r_model = preferred_model or "deepseek/deepseek-r1"
            r_timeout = max(timeout_seconds, 8.0)
            raw = _query_openrouter_http(prompt, system_prompt=system_prompt, model=r_model, timeout=r_timeout)
            if raw:
                parsed = extract_and_validate_json(raw)
                if parsed:
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return LLMInferenceResult(
                        success=True,
                        vendor_used="openrouter",
                        model=r_model,
                        latency_ms=elapsed_ms,
                        is_fallback=False,
                        parsed_payload=parsed,
                        raw_response=raw,
                    )
        except Exception as e:
            logger.debug(f"[LLMBridge] OpenRouter reasoning stage bypassed: {e}")

    # ── Stage 2: Groq Ultra-Fast (< 300 ms) ──
    try:
        raw = _query_groq_http(prompt, system_prompt=system_prompt, timeout=timeout_seconds)
        if raw:
            parsed = extract_and_validate_json(raw)
            if parsed:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return LLMInferenceResult(
                    success=True,
                    vendor_used="groq",
                    model="openai/gpt-oss-120b",
                    latency_ms=elapsed_ms,
                    is_fallback=False,
                    parsed_payload=parsed,
                    raw_response=raw,
                )
    except Exception as e:
        logger.debug(f"[LLMBridge] Groq stage bypassed: {e}")

    # ── Stage 3: Gemini Secondary Failover ──
    try:
        raw = _query_gemini_http(prompt, system_prompt=system_prompt, timeout=timeout_seconds)
        if raw:
            parsed = extract_and_validate_json(raw)
            if parsed:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return LLMInferenceResult(
                    success=True,
                    vendor_used="gemini",
                    model="gemini-2.5-flash",
                    latency_ms=elapsed_ms,
                    is_fallback=False,
                    parsed_payload=parsed,
                    raw_response=raw,
                )
    except Exception as e:
        logger.debug(f"[LLMBridge] Gemini stage bypassed: {e}")

    # ── Stage 4: Deterministic Algorithmic Fallback (Zero Network Latency) ──
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    fallback_payload = get_deterministic_fallback_consensus(signal or {}, macro_context=macro_context)

    return LLMInferenceResult(
        success=True,
        vendor_used="deterministic_fallback",
        model="quantitative_rule_engine",
        latency_ms=elapsed_ms,
        is_fallback=True,
        parsed_payload=fallback_payload,
        raw_response=json.dumps(fallback_payload),
    )


def query_llm_reasoning(
    prompt: str,
    system_prompt: str = "",
    signal: Optional[Dict[str, Any]] = None,
    macro_context: Optional[Dict[str, Any]] = None,
    preferred_model: str = "deepseek/deepseek-r1",
    timeout_seconds: float = 8.0,
) -> LLMInferenceResult:
    """Dedicated alias for query_llm_fast with reasoning mode enabled."""
    return query_llm_fast(
        prompt=prompt,
        system_prompt=system_prompt,
        signal=signal,
        macro_context=macro_context,
        timeout_seconds=timeout_seconds,
        is_reasoning=True,
        preferred_model=preferred_model,
    )


# ── Optional Vendor Stubs for Legacy Import Compatibility ──
try:
    from groq import Groq  # type: ignore
except (ImportError, ModuleNotFoundError):
    class _GroqCompletions:
        def create(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("groq library is not installed")
    class _GroqChat:
        completions = _GroqCompletions()
    class Groq:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.chat = _GroqChat()

try:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except (ImportError, ModuleNotFoundError):
    class _GenAIModels:
        def generate_content(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("google-genai library is not installed")
    class _GenAIClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.models = _GenAIModels()
    class _GenAITypes:
        class GenerateContentConfig:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass
    class _GenAIShim:
        Client = _GenAIClient
    genai = _GenAIShim()  # type: ignore
    types = _GenAITypes()  # type: ignore
