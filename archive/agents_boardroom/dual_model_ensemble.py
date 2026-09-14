"""
Module: agents/dual_model_ensemble.py
Purpose: SOTA Intra-Persona Dual-Model Cross-Validation Ensemble for MJONAI.
         Queries two independent, diverse frontier LLM families concurrently:
           - Model A: Groq Open-Weights LPU (Llama / Qwen / GPT-OSS)
           - Model B: Google Gemini API (Gemini 2.5 / 1.5 Flash)
         Cross-validates their independent reasoning to eliminate single-model bias,
         detect subtle blindspots, and calculate high-conviction blended consensus.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from mjonai.agents.llm_bridge import (
    _query_groq_http,
    _query_gemini_http,
    extract_and_validate_json,
    LLMInferenceResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DualModelResponse:
    """Immutable contract representing the blended cross-validation of two independent models."""
    verdict: str                  # APPROVE, VETO, CAUTION, NEUTRAL
    blended_confidence: int       # 0 to 100
    model_a_verdict: str
    model_a_confidence: int
    model_b_verdict: str
    model_b_confidence: int
    is_cross_model_agreement: bool
    discrepancy_detected: bool
    combined_reasons: List[str]
    combined_red_flags: List[str]
    models_used: str
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def query_dual_model_ensemble(
    prompt: str,
    system_prompt: str = "",
    persona_name: str = "SPECIALIST",
    timeout_seconds: float = 3.5,
) -> DualModelResponse:
    """
    Query Groq and Google Gemini in parallel asynchronous threads and synthesize cross-model consensus.
    """
    t0 = time.perf_counter()

    groq_raw: Optional[str] = None
    gemini_raw: Optional[str] = None

    def _call_groq():
        return _query_groq_http(prompt, system_prompt=system_prompt, timeout=timeout_seconds)

    def _call_gemini():
        return _query_gemini_http(prompt, system_prompt=system_prompt, timeout=timeout_seconds)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_groq = executor.submit(_call_groq)
        f_gem = executor.submit(_call_gemini)

        try:
            groq_raw = f_groq.result(timeout=timeout_seconds)
        except Exception as e:
            logger.debug(f"[DualEnsemble] Groq thread timeout/error: {e}")

        try:
            gemini_raw = f_gem.result(timeout=timeout_seconds)
        except Exception as e:
            logger.debug(f"[DualEnsemble] Gemini thread timeout/error: {e}")

    data_a = extract_and_validate_json(groq_raw or "")
    data_b = extract_and_validate_json(gemini_raw or "")

    latency = (time.perf_counter() - t0) * 1000.0

    # Case 1: Both models responded successfully
    if data_a and data_b:
        v_a = str(data_a.get("verdict", "NEUTRAL")).upper()
        v_b = str(data_b.get("verdict", "NEUTRAL")).upper()
        c_a = int(data_a.get("confidence", 50))
        c_b = int(data_b.get("confidence", 50))

        reasons = list(dict.fromkeys((data_a.get("key_reasons") or []) + (data_b.get("key_reasons") or [])))
        red_flags = list(dict.fromkeys((data_a.get("red_flags") or []) + (data_b.get("red_flags") or [])))

        is_agree = (v_a == v_b)
        blended_conf = int((c_a + c_b) / 2.0)

        if is_agree:
            final_v = v_a
            discrepancy = False
        else:
            discrepancy = True
            # Conservative consensus: if either model issues VETO or CAUTION, adopt the more defensive stance
            if "VETO" in (v_a, v_b):
                final_v = "VETO"
                blended_conf = max(c_a, c_b)
            elif "CAUTION" in (v_a, v_b):
                final_v = "CAUTION"
                blended_conf = 60
            else:
                final_v = "NEUTRAL"
                blended_conf = 50

        return DualModelResponse(
            verdict=final_v,
            blended_confidence=blended_conf,
            model_a_verdict=v_a,
            model_a_confidence=c_a,
            model_b_verdict=v_b,
            model_b_confidence=c_b,
            is_cross_model_agreement=is_agree,
            discrepancy_detected=discrepancy,
            combined_reasons=reasons[:4],
            combined_red_flags=red_flags[:3],
            models_used="Groq(Llama/Qwen)+Google(Gemini)",
            latency_ms=round(latency, 1),
        )

    # Case 2: Only Groq succeeded
    elif data_a:
        v_a = str(data_a.get("verdict", "NEUTRAL")).upper()
        c_a = int(data_a.get("confidence", 50))
        return DualModelResponse(
            verdict=v_a,
            blended_confidence=c_a,
            model_a_verdict=v_a,
            model_a_confidence=c_a,
            model_b_verdict="OFFLINE",
            model_b_confidence=0,
            is_cross_model_agreement=True,
            discrepancy_detected=False,
            combined_reasons=data_a.get("key_reasons") or [],
            combined_red_flags=data_a.get("red_flags") or [],
            models_used="Groq(Single)",
            latency_ms=round(latency, 1),
        )

    # Case 3: Only Gemini succeeded
    elif data_b:
        v_b = str(data_b.get("verdict", "NEUTRAL")).upper()
        c_b = int(data_b.get("confidence", 50))
        return DualModelResponse(
            verdict=v_b,
            blended_confidence=c_b,
            model_a_verdict="OFFLINE",
            model_a_confidence=0,
            model_b_verdict=v_b,
            model_b_confidence=c_b,
            is_cross_model_agreement=True,
            discrepancy_detected=False,
            combined_reasons=data_b.get("key_reasons") or [],
            combined_red_flags=data_b.get("red_flags") or [],
            models_used="Gemini(Single)",
            latency_ms=round(latency, 1),
        )

    # Case 4: Both offline -> Deterministic neutral fallback
    else:
        return DualModelResponse(
            verdict="NEUTRAL",
            blended_confidence=50,
            model_a_verdict="OFFLINE",
            model_a_confidence=0,
            model_b_verdict="OFFLINE",
            model_b_confidence=0,
            is_cross_model_agreement=True,
            discrepancy_detected=False,
            combined_reasons=["LLM APIs offline - deterministic fallback"],
            combined_red_flags=[],
            models_used="DETERMINISTIC_FALLBACK",
            latency_ms=round(latency, 1),
        )
