"""
Module: knowledge/retriever.py
Purpose: Fast Knowledge & Rationale Retriever.
         Provides instant contextual trading wisdom to Bull, Bear, and Supervisor agents
         and answers user questions about market concepts and risk rules.
"""

import re
import logging
from typing import List, Dict, Any

from knowledge.principles import TRADING_PRINCIPLES

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> set:
    """Extract lowercase alpha tokens from string."""
    return set(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))


def retrieve_knowledge(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Retrieve most relevant quantitative and trading principles for a query.

    Args:
        query: Search query or trade context (e.g. "breakout volume", "consecutive losses cooldown")
        top_k: Number of principles to return

    Returns:
        List of matched principle dicts sorted by relevance score
    """
    if not query:
        return TRADING_PRINCIPLES[:top_k]

    query_tokens = _tokenize(query)
    scored = []

    for item in TRADING_PRINCIPLES:
        # Match against tags, title, content, and category
        tag_tokens = set(item.get("tags", []))
        content_tokens = _tokenize(item.get("title", "") + " " + item.get("content", "") + " " + item.get("category", ""))

        # Tag matches count 3x, content matches count 1x
        tag_overlap = len(query_tokens.intersection(tag_tokens)) * 3.0
        content_overlap = len(query_tokens.intersection(content_tokens)) * 1.0
        total_score = tag_overlap + content_overlap

        if total_score > 0:
            scored.append((total_score, item))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        return [item for score, item in scored[:top_k]]

    # Fallback to default top principles if no specific match
    return TRADING_PRINCIPLES[:top_k]
