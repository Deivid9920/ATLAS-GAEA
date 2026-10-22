"""Prompt-injection fencing (#10).

Every text that did not originate inside ATLAS (web pages, files, tool
outputs, bridge payloads) enters the pipeline wrapped in <untrusted>
fences. The orchestrator NEVER interprets tool commands from fenced
text: action extraction only recognizes commands written outside the
fences, by the ATLAS planner itself. A fenced payload can say
"run hephaestus" a thousand times — it stays data, never instructions.
"""

from __future__ import annotations

import re

OPEN = "<untrusted>"
CLOSE = "</untrusted>"

# command-like patterns the orchestrator would treat as instructions if
# they appeared OUTSIDE a fence
_TOOL_CMD = re.compile(
    r"\b(tool_call|atlas\.(?:generate|verify)|run\s+tool|execute\s+tool)"
    r"\b\s*[:=]?", re.IGNORECASE)


def fence(text: str) -> str:
    """Wrap external text in the untrusted fence."""
    body = str(text)
    if CLOSE in body:  # escape attempts: break nested close tags
        body = body.replace(CLOSE, "<\\/untrusted>")
    return f"{OPEN}\n{body}\n{CLOSE}"


def _outside_fences(text: str) -> str:
    """Return only the segments of text that are OUTSIDE fences."""
    parts: list[str] = []
    rest = text
    while True:
        start = rest.find(OPEN)
        if start == -1:
            parts.append(rest)
            break
        parts.append(rest[:start])
        end = rest.find(CLOSE, start + len(OPEN))
        if end == -1:  # unclosed fence: everything after OPEN is data
            break
        rest = rest[end + len(CLOSE):]
    return "".join(parts)


def is_fenced(text: str) -> bool:
    return OPEN in text and CLOSE in text


def strip_fence(text: str) -> str:
    """Payload of the FIRST fence (the data, not its cage)."""
    start = text.find(OPEN)
    if start == -1:
        return text
    body_start = start + len(OPEN)
    end = text.find(CLOSE, body_start)
    if end == -1:
        return text[body_start:]
    return text[body_start:end].strip("\n")


def contains_tool_command(text: str) -> bool:
    """True only when a tool-command pattern appears OUTSIDE fences.

    Fenced tool commands are inert data by contract: this is the check
    the runner applies before honoring anything a tool produced.
    """
    return bool(_TOOL_CMD.search(_outside_fences(text)))


def tool_commands_in_fenced_text(text: str) -> list[str]:
    """Diagnostic: commands an attacker attempted to smuggle inside
    fences (reported to the audit chain, never executed)."""
    hits: list[str] = []
    for match in re.finditer(
            re.escape(OPEN) + r"(.*?)" + re.escape(CLOSE), text, re.S):
        hits.extend(m.group(0) for m in _TOOL_CMD.finditer(match.group(1)))
    return hits
