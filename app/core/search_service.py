"""
TextGrid interval search service.
Independent of GUI. Expects a list of intervals in the format:
[
    {
        "text": str,
        "tier": str,
        "file": str,
        "start": float,
        "end": float
    },
    ...
]
"""

import re
from typing import List, Dict, Any


def search_intervals(
    intervals: List[Dict[str, Any]],
    pattern: str,
    context_size: int = 3,
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
) -> List[Dict[str, Any]]:
    """
    Returns a list of intervals where the pattern is found.
    Each result contains:
        - file: filename
        - tier: tier name
        - start, end: time boundaries
        - match_text: text fragment with context (context_size characters before/after)
        - full_text: original interval text
    """

    if not pattern:
        return []
    pat = re.compile(pattern, flags)
    results = []
    for iv in intervals:
        match = pat.search(iv["text"])
        if match:
            start_idx = max(0, match.start() - context_size)
            end_idx = min(match.end() + context_size, len(iv["text"]))
            prefix = "..." if start_idx > 0 else ""
            suffix = "..." if end_idx < len(iv["text"]) else ""
            context = prefix + iv["text"][start_idx:end_idx] + suffix
            results.append(
                {
                    "file": iv["file"],
                    "tier": iv["tier"],
                    "start": iv["start"],
                    "end": iv["end"],
                    "match_text": context,
                    "full_text": iv["text"],
                }
            )
    return results
