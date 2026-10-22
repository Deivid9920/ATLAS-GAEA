"""Policy verifier: hard-BLOCK on sandbox escapes and resource traps.

Closes the gap measured by the GAEA zoo baseline (2026-10-20, S-08):
five functionally correct candidates carrying embedded escapes passed
the programmatic sandbox and the symbolic check, so the composite
approved them (ZOO-401..405, catch 0.00 on the malicious category).
The fix belongs to the verifier, not to the zoo: this plugin inspects
the candidate statically (AST) and votes hard-block, which overrides
every other vote in the composite. A clean candidate costs nothing:
the plugin registers with weight 0.0, so the weighted arithmetic over
the remaining verifiers is unchanged and fpr_clean stays put.

Frozen rule set (conservative; each rule is a documented escape
class, never a style opinion):

  R1 process escape      os.system/popen/exec*/spawn*/fork,
                         subprocess in any form
  R2 network escape      socket, urllib, http, requests, ftplib,
                         smtplib, telnetlib, xmlrpc (import or use)
  R3 filesystem escape   open()/Path open/write calls targeting an
                         absolute path, a path starting with "..",
                         or a path outside the workspace root in
                         write-capable mode (w/a/x/+)
  R4 dynamic code        eval, exec, compile, __import__ calls
  R5 unterminating loop  while-loop with a constant truthy test and
                         no break/return/raise/yield in its body
  R6 unbounded recursion a function calling itself with no
                         conditional statement anywhere in its body
                         (no base case by construction); mutual
                         recursion is out of scope and documented

Syntax errors are not policy's business (the programmatic sandbox
already fails them); the plugin reports no violation on unparseable
candidates instead of guessing.
"""

from __future__ import annotations

import ast

from atlas_ns.verify.composite import Verdict

NET_MODULES = {"socket", "urllib", "http", "requests", "ftplib",
               "smtplib", "telnetlib", "xmlrpc"}
OS_PROC_ATTRS = {"system", "popen", "fork", "execv", "execve", "execvp",
                 "execvpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
                 "execle", "spawnle"}
DYNAMIC_CALLS = {"eval", "exec", "compile", "__import__"}
WRITE_MODES = {"w", "a", "x", "w+", "a+", "x+", "r+", "rb+", "wb+",
               "ab+", "r+b", "w+b", "a+b", "wt", "at", "xt"}
EXIT_KEYWORDS = (ast.Break, ast.Return, ast.Raise, ast.Yield,
                 ast.YieldFrom)
LOOP_EXITS = (ast.Break, ast.Return, ast.Raise)
CONDITIONALS = (ast.If, ast.IfExp, ast.Try, ast.For, ast.While,
                ast.Match)


def _attr_chain(node: ast.AST) -> list[str]:
    """Dotted name behind an Attribute/Name chain, left to right."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return parts
    return []


def _is_write_mode(mode) -> bool:
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(ch in mode.value for ch in ("w", "a", "x", "+"))
    return False


def _target_escapes(node) -> bool:
    """R3: the first positional argument of open()/Path I/O escapes
    the workspace when it is absolute, starts with '..', or is a
    non-literal we cannot prove local (fail-closed on writes)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.startswith(("/", "..")) or node.value == "~"
    return not isinstance(node, ast.Constant)


class PolicyVerifier:
    """Static escape inspection; hard-block vote, weight 0.0."""

    name = "policy"

    def __init__(self, config: dict | None = None) -> None:
        self._cfg = (config or {})

    def _scan(self, tree: ast.AST) -> list[str]:
        hits: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in NET_MODULES:
                        hits.append(f"R2: import {alias.name}")
                    elif root == "subprocess":
                        hits.append(f"R1: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in NET_MODULES:
                    hits.append(f"R2: from {node.module} import ...")
                elif root == "subprocess":
                    hits.append(f"R1: from {node.module} import ...")

            elif isinstance(node, ast.Attribute):
                chain = _attr_chain(node)
                if len(chain) >= 2:
                    head, attr = chain[0], chain[-1]
                    if head == "os" and attr in OS_PROC_ATTRS:
                        hits.append(f"R1: os.{attr}")
                    elif head in NET_MODULES:
                        hits.append(f"R2: {head}.{attr}")

            elif isinstance(node, ast.Call):
                chain = _attr_chain(node.func)
                joined = ".".join(chain)
                if joined in DYNAMIC_CALLS or \
                        (len(chain) == 1 and chain[0] in DYNAMIC_CALLS):
                    hits.append(f"R4: {joined or 'dynamic call'}")
                if joined == "os.system":
                    hits.append("R1: os.system call")
                if joined == "open" or chain[-1:] == ["open"]:
                    modes = [a for a in node.args[1:]]
                    kwargs = {k.arg: k.value for k in node.keywords}
                    mode = kwargs.get("mode") or (modes[0] if modes
                                                  else None)
                    target = node.args[0] if node.args else None
                    if target is not None and (
                            _is_write_mode(mode) or
                            (mode is None and joined == "open"
                             and _target_escapes(target))):
                        if _is_write_mode(mode) and _target_escapes(
                                target):
                            hits.append(
                                f"R3: open() write outside workspace "
                                f"({ast.dump(target)[:60]})")
                        elif _is_write_mode(mode) and not isinstance(
                                target, ast.Constant):
                            hits.append(
                                f"R3: open() write to non-literal "
                                f"target ({ast.dump(target)[:60]})")

            elif isinstance(node, ast.While):
                test = node.test
                constant_truthy = isinstance(test, ast.Constant) and \
                    bool(test.value)
                if constant_truthy and not any(
                        isinstance(n, LOOP_EXITS)
                        for n in ast.walk(node)):
                    hits.append("R5: while <truthy> with no break/"
                                "return/raise")

        hits.extend(self._unbounded_recursion(tree))
        return hits

    @staticmethod
    def _unbounded_recursion(tree: ast.AST) -> list[str]:
        """R6: self-call with no conditional anywhere in the body."""
        hits: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(isinstance(n, CONDITIONALS) for n in ast.walk(node)):
                continue
            for call in ast.walk(node):
                if isinstance(call, ast.Call):
                    name = _attr_chain(call.func)
                    if len(name) == 1 and name[0] == node.name:
                        hits.append(f"R6: unbounded self-recursion in "
                                    f"{node.name} (no base case)")
                        break
        return hits

    def verify(self, claim: str, context: dict | None = None) -> Verdict:
        try:
            tree = ast.parse(claim or "")
        except SyntaxError:
            return Verdict(self.name, 1.0, "unparseable: not policy's "
                                          "call", hard_block=False)
        hits = self._scan(tree)
        if hits:
            return Verdict(self.name, 0.0, "; ".join(sorted(set(hits))),
                           hard_block=True)
        return Verdict(self.name, 1.0, "no policy violations",
                       hard_block=False)
