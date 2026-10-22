"""Tool permissions (#11): {readonly, write, execute} per tool.

Fail-closed: a tool missing from the table has NO permission; a check
for an unlisted tool is a violation, not an implicit allow. Every check
returns an audit event for the chain — permissions are visible.
"""

from __future__ import annotations

from enum import Enum

LEVELS = ("readonly", "write", "execute")


class PermissionError(Exception):
    """Raised by require() when a tool lacks the needed level."""


class Perm(str, Enum):
    READONLY = "readonly"
    WRITE = "write"
    EXECUTE = "execute"

    @property
    def rank(self) -> int:
        return LEVELS.index(self.value)


class PermissionTable:
    def __init__(self, grants: dict[str, str] | None = None) -> None:
        self._grants: dict[str, Perm] = {}
        for tool, level in (grants or {}).items():
            if level not in LEVELS:
                raise ValueError(f"bad permission level {level!r} for "
                                 f"{tool!r}; expected one of {LEVELS}")
            self._grants[tool] = Perm(level)

    def grant(self, tool: str, level: str) -> None:
        if level not in LEVELS:
            raise ValueError(f"bad permission level {level!r}")
        self._grants[tool] = Perm(level)

    def check(self, tool: str, needed: str | Perm) -> bool:
        """Fail-closed check: unknown tool or unknown level -> False."""
        needed = Perm(needed) if not isinstance(needed, Perm) else needed
        granted = self._grants.get(tool)
        if granted is None:
            return False
        return granted.rank >= needed.rank

    def require(self, tool: str, needed: str | Perm) -> dict:
        """Check + audit event; raises PermissionError when denied."""
        needed = Perm(needed) if not isinstance(needed, Perm) else needed
        allowed = self.check(tool, needed)
        event = {
            "action": "permission_check",
            "tool": tool,
            "needed": needed.value,
            "granted": self._grants.get(tool).value
            if tool in self._grants else None,
            "allowed": allowed,
        }
        if not allowed:
            raise PermissionError(
                f"tool {tool!r} lacks {needed.value!r} "
                f"(grants: {sorted(self._grants)})")
        return event

    def grants(self) -> dict[str, str]:
        return {tool: perm.value for tool, perm in sorted(self._grants.items())}


def from_config(config: dict) -> PermissionTable:
    """Build the table from config.safety.permissions; fail-closed."""
    safety = config.get("safety", {}) or {}
    return PermissionTable(dict(safety.get("permissions", {}) or {}))
