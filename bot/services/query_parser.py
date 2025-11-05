from __future__ import annotations

import re
from typing import List


DELIMITERS_RE = re.compile(r"[,\.\n;]+")


def split_queries(text: str) -> List[str]:
    candidates = DELIMITERS_RE.split(text)
    cleaned = []
    seen = set()
    for item in candidates:
        normalized = item.strip()
        if not normalized:
            continue
        lower = normalized.lower()
        if lower in seen:
            continue
        seen.add(lower)
        cleaned.append(normalized)
    return cleaned

