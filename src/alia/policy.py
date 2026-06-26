"""Approval policy for ALIA's bash gate.

Two ways a command skips the prompt:
1. it's on the built-in read-only allowlist (`is_auto_safe`), or
2. its prefix was approved earlier this session (`matches_prefix`).

A hard safety floor sits under both: a command containing shell operators
(pipes, redirects, chaining, command substitution, newlines) is NEVER
auto-approved — it always prompts. That stops a safe leading command from
smuggling a dangerous one (`ls; rm -rf ~`). Hard red-lines (sudo, rm -rf /)
are blocked outright upstream by lovelaice's bash_prefix_guard.
"""

from __future__ import annotations

import re
import shlex

# Operators that always force a prompt: redirects (write files) and command
# substitution (run arbitrary code). No reasoning about safety past these.
_DISQUALIFYING = (">", "<", "`", "$(", "${", "\n")
# Operators that merely *compose* commands. A pipeline/chain auto-runs only if
# EVERY segment between them is itself allowlist-safe (so `ls | wc` is fine,
# `ls | sh` is not).
_SPLIT_RE = re.compile(r"&&|\|\||;|\|")

# Well-known read-only / inert commands, safe to run without asking.
SAFE_COMMANDS = {
    "ls", "pwd", "cat", "echo", "printf", "head", "tail", "wc", "grep", "egrep",
    "fgrep", "rg", "which", "type", "whoami", "id", "date", "uname", "df", "du",
    "free", "uptime", "ps", "env", "printenv", "stat", "file", "tree", "hostname",
    "basename", "dirname", "realpath", "readlink", "sort", "uniq", "cut", "nl",
    "column", "fold", "comm", "diff", "cmp", "lsblk", "lscpu", "lsusb", "lspci",
    "whereis", "cal", "arch", "nproc", "tty", "groups", "locate",
}

# Multi-verb tools whose safe sub-commands auto-run; others prompt.
SAFE_SUBCOMMANDS = {
    "git": {"status", "log", "diff", "show", "blame", "shortlog", "remote",
            "rev-parse", "ls-files", "ls-remote", "describe"},
    "docker": {"ps", "images", "logs", "inspect", "version", "info", "stats"},
    "podman": {"ps", "images", "logs", "inspect", "version", "info", "stats"},
    "systemctl": {"status", "is-active", "is-enabled", "list-units",
                  "list-unit-files", "show", "cat"},
    "flatpak": {"list", "info", "search"},
}

# Tools for which the session-approval prefix is "<tool> <verb>" (more granular
# than the bare binary), so approving `git log` doesn't also allow `git push`.
_MULTI_VERB = set(SAFE_SUBCOMMANDS) | {
    "npm", "pnpm", "yarn", "cargo", "go", "pip", "pip3", "uv", "make", "apt",
    "dnf", "gh", "kubectl", "brew",
}


def has_disqualifying(command: str) -> bool:
    """Redirect / substitution present → always prompt, never auto-run."""
    return any(op in command for op in _DISQUALIFYING)


def has_split(command: str) -> bool:
    """A pipe/chain operator is present (`|`, `;`, `&&`, `||`)."""
    return _SPLIT_RE.search(command) is not None


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def approval_prefix(command: str) -> str:
    """The prefix a session-approval grants. `<tool> <verb>` for multi-verb
    tools (first non-flag arg), else the bare binary."""
    toks = _tokens(command)
    if not toks:
        return ""
    head = toks[0]
    if head in _MULTI_VERB:
        for t in toks[1:]:
            if not t.startswith("-"):
                return f"{head} {t}"
    return head


def _segment_safe(segment: str) -> bool:
    toks = _tokens(segment)
    if not toks:
        return False
    head = toks[0]
    if head in SAFE_SUBCOMMANDS:
        return len(toks) > 1 and toks[1] in SAFE_SUBCOMMANDS[head]
    return head in SAFE_COMMANDS


def is_auto_safe(command: str) -> bool:
    """True if the command may run without asking.

    No redirect/substitution, and every pipeline/chain segment is itself an
    allowlisted read-only command (so `ls | wc -l` auto-runs, `ls | sh` does not).
    """
    if has_disqualifying(command):
        return False
    segments = [s.strip() for s in _SPLIT_RE.split(command) if s.strip()]
    return bool(segments) and all(_segment_safe(s) for s in segments)


def matches_prefix(command: str, approved_prefixes: set[str]) -> bool:
    """True if a simple (operator-free) command's prefix was approved this session."""
    if has_disqualifying(command) or has_split(command):
        return False
    return approval_prefix(command) in approved_prefixes
