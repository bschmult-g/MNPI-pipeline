"""Search and verification tools for SA3 (Public Check).

Provides capabilities to:
1. Check public press / SEC filings for material statements (Mosaic Theory check).
2. Scan text for linguistic secrecy and confidentiality markers ("don't share", "confidential").
"""

from __future__ import annotations

import re
from typing import Dict, List
from config import settings


# Pre-populated mock database of public press releases and SEC filings
# In production, this connects to Google Search / Vertex Discovery / SEC EDGAR API
MOCK_PUBLIC_RECORDS = {
    "target": "Target Corporation (NYSE: TGT) publicly reported Q2 financial results on August 21, confirming 2.7% comparable sales growth and reaffirming full-year guidance.",
    "apple": "Apple Inc. announced the official public launch date for iOS 18 and new hardware devices at the September public keynote event.",
    "microsoft": "Microsoft Corp announced the general commercial availability of Copilot Studio updates via an official press release on microsoft.com.",
    "alpha": "Alpha Corp filed an 8-K with the SEC announcing the completion of the acquisition of Beta Software for $450M in cash and stock.",
}


def search_public_press_and_filings(query: str) -> str:
    """Searches top-tier news wires (Bloomberg, Reuters), SEC EDGAR, and corporate PR.

    Use this tool to verify whether an acquisition, product release, or corporate
    event has ALREADY been officially disclosed to the public.

    Args:
        query: Company name, ticker, or topic to search (e.g. 'Alpha Corp acquisition', 'Target earnings')

    Returns:
        Summary of verified public articles or filings found, or a notice that NO public record exists.
    """
    clean_query = query.lower()
    matched_records = []

    for key, record in MOCK_PUBLIC_RECORDS.items():
        if key in clean_query:
            matched_records.append(record)

    if matched_records:
        return "PUBLIC RECORDS FOUND:\n" + "\n".join(f"- {r}" for r in matched_records)
    else:
        return (
            f"NO PUBLIC FILINGS OR TOP-TIER PRESS FOUND for query: '{query}'.\n"
            f"Searched: {', '.join(settings.trusted_public_sources[:5])}.\n"
            f"Status: INFORMATION APPEARS NON-PUBLIC."
        )


def detect_secrecy_markers(text: str) -> List[str]:
    """Scans text for explicit linguistic secrecy and confidentiality markers.

    Finds indicators like "don't share", "keep quiet", "confidential", "internal only".

    Args:
        text: The raw communication or document text.

    Returns:
        List of identified secrecy markers.
    """
    found_markers = []
    lower_text = text.lower()

    for marker in settings.secrecy_markers:
        # Match whole phrase or with flexible punctuation
        pattern = r"\b" + re.escape(marker) + r"\b"
        if re.search(pattern, lower_text):
            found_markers.append(marker)

    return found_markers
