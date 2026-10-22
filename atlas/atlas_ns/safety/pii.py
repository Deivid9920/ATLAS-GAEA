"""PII scrubber (#24): local regex + dictionaries, BEFORE personal text
enters memory or the graph. Counts are audited; contents never are.

Categories: emails, phones, card-like numbers, custom dictionary terms
(names, ids). Replacement is a typed placeholder so downstream tools
still see sentence structure.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern] = {
    # order matters: longest runs first so a 16-digit card is not eaten
    # by the phone pattern's shorter match
    "card": re.compile(r"(?<!\w)(?:\d[ -]?){13,16}(?!\w)"),
    "iban": re.compile(r"(?<!\w)[A-Z]{2}\d{2}[A-Z0-9]{10,30}(?!\w)"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(
        r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?"
        r"\d{2,4}(?:[\s.-]?\d{2,4}){1,3}(?!\w)"),
}

PLACEHOLDERS = {"email": "[EMAIL]", "phone": "[PHONE]",
                "card": "[CARD]", "iban": "[IBAN]"}


class PIIScrubber:
    def __init__(self, config: dict | None = None,
                 extra_terms: list[str] | None = None) -> None:
        self.enabled = bool((config or {}).get("safety", {})
                            .get("pii_scrub", True))
        terms = list(extra_terms or [])
        if terms:
            # dictionary terms: longest-first so phrases win over words
            escaped = sorted((re.escape(t) for t in terms), key=len,
                             reverse=True)
            self._dict_re = re.compile("|".join(escaped), re.IGNORECASE) \
                if escaped else None
        else:
            self._dict_re = None

    def scrub(self, text: str) -> tuple[str, dict[str, int]]:
        """Return (clean_text, counts_per_category)."""
        counts: dict[str, int] = {}
        if not self.enabled or not text:
            return text, counts
        clean = text
        for cat, pattern in PATTERNS.items():
            clean, n = pattern.subn(PLACEHOLDERS[cat], clean)
            if n:
                counts[cat] = counts.get(cat, 0) + n
        if self._dict_re is not None:
            clean, n = self._dict_re.subn("[REDACTED]", clean)
            if n:
                counts["dictionary"] = counts.get("dictionary", 0) + n
        return clean, counts

    def scrub_audit_event(self, text: str) -> tuple[str, dict]:
        """Scrub + build the AUDIT event (counts only, zero contents)."""
        clean, counts = self.scrub(text)
        return clean, {"action": "pii_scrub",
                       "categories": counts,
                       "total": sum(counts.values()),
                       "content_in_audit": False}
