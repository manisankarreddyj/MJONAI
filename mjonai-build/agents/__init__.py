"""
Module: agents/__init__.py
Purpose: SOTA Multi-Agent Consensus Room & Post-Trade Reflection Package
         (Bull Technical Analyst, Bear Adversarial Risk Sentry, Supervisor CIO Arbiter,
          Quant Mathematics & Microstructure Auditor, Debate Room Deliberator,
          Post-Trade Critic, and Universal LLM Bridge).
"""

from agents.llm_bridge import (
    query_llm_fast,
    extract_and_validate_json,
    get_deterministic_fallback_consensus,
    LLMInferenceResult,
)
from agents.bull import (
    analyse as analyse_bull,
    BullAgentResult,
)
from agents.bear import (
    analyse as analyse_bear,
    BearAgentResult,
)
from agents.supervisor import (
    evaluate as evaluate_supervisor,
    SupervisorEvaluationResult,
)
from agents.macro_specialist import (
    analyse_macro_flow,
    MacroSpecialistResult,
)
from agents.quant_auditor import (
    audit_quantitative_integrity,
    QuantAuditorResult,
)
from agents.debate_room import (
    conduct_adversarial_debate,
    DebateTranscript,
    DebateConsensusResult,
)
from agents.critic import (
    reflect_on_closed_trade,
    TradeReflectionResult,
)

__all__ = [
    # 1. Universal Multi-LLM Bridge
    "query_llm_fast",
    "extract_and_validate_json",
    "get_deterministic_fallback_consensus",
    "LLMInferenceResult",
    # 2. Bull Technical Analyst
    "analyse_bull",
    "BullAgentResult",
    # 3. Bear Adversarial Risk Sentry
    "analyse_bear",
    "BearAgentResult",
    # 4. Macro & Institutional Flow Specialist
    "analyse_macro_flow",
    "MacroSpecialistResult",
    # 5. Quantitative & Microstructure Auditor
    "audit_quantitative_integrity",
    "QuantAuditorResult",
    # 6. Supervisor CIO Arbiter
    "evaluate_supervisor",
    "SupervisorEvaluationResult",
    # 7. Debate Room Consensus
    "conduct_adversarial_debate",
    "DebateTranscript",
    "DebateConsensusResult",
    # 8. Post-Trade Critic
    "reflect_on_closed_trade",
    "TradeReflectionResult",
]
