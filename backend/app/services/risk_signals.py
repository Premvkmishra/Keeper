"""Deterministic social-engineering / urgency signals. Not LLM-based."""
import re
from typing import List

URGENCY_PATTERNS = [
    re.compile(r"pay immediately", re.I),
    re.compile(r"disconnected", re.I),
    re.compile(r"do not call customer support", re.I),
    re.compile(r"ignore previous", re.I),
    re.compile(r"change the destination", re.I),
    re.compile(r"new beneficiary", re.I),
    re.compile(r"do not tell anyone", re.I),
    re.compile(r"keep this (secret|private)", re.I),
    re.compile(r"electricity will be (cut|disconnected)", re.I),
    re.compile(r"deadline is urgent", re.I),
]


def detect_risk_signals(*texts: str) -> List[str]:
    blob = " ".join(t for t in texts if t)
    hits: List[str] = []
    for pat in URGENCY_PATTERNS:
        if pat.search(blob):
            hits.append(pat.pattern)
    return hits
