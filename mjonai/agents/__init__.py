"""
Module: agents/__init__.py
Purpose: SOTA Multi-Agent Consensus Room & Post-Trade Reflection Package
         (Bull Technical Analyst, Bear Adversarial Risk Sentry, Supervisor CIO Arbiter,
          Debate Room Deliberator, Post-Trade Critic, and Universal LLM Bridge).
"""

from mjonai.agents.llm_bridge import (
    query_llm_fast,
    extract_and_validate_json,
    get_deterministic_fallback_consensus,
    LLMInferenceResult,
)
from mjonai.agents.bull import (
    analyse as analyse_bull,
    BullAgentResult,
)
from mjonai.agents.bear import (
    analyse as analyse_bear,
    BearAgentResult,
)
from mjonai.agents.supervisor import (
    evaluate as evaluate_supervisor,
    SupervisorEvaluationResult,
)
from mjonai.agents.macro_specialist import (
    analyse_macro_flow,
    MacroSpecialistResult,
)
from mjonai.agents.debate_room import (
    conduct_adversarial_debate,
    DebateTranscript,
    DebateConsensusResult,
)
from mjonai.agents.critic import (
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
    # 5. Supervisor CIO Arbiter
    "evaluate_supervisor",
    "SupervisorEvaluationResult",
    # 6. Debate Room Consensus
    "conduct_adversarial_debate",
    "DebateTranscript",
    "DebateConsensusResult",
    # 7. Post-Trade Critic
    "reflect_on_closed_trade",
    "TradeReflectionResult",
]
