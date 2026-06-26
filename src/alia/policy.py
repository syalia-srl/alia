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

import shlex

# Shell control that could chain/redirect/substitute — disqualifies auto-approval.
_OPERATORS = (";", "&&", "||", "|", ">", "<", "`", "$(", "${", "\n")

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


def has_operators(command: str) -> bool:
    return any(op in command for op in _OPERATORS)


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


def is_auto_safe(command: str) -> bool:
    """True if the command may run without asking (read-only allowlist)."""
    if has_operators(command):
        return False
    toks = _tokens(command)
    if not toks:
        return False
    head = toks[0]
    if head in SAFE_SUBCOMMANDS:
        return len(toks) > 1 and toks[1] in SAFE_SUBCOMMANDS[head]
    return head in SAFE_COMMANDS


def matches_prefix(command: str, approved_prefixes: set[str]) -> bool:
    """True if this command's prefix was approved for the session."""
    if has_operators(command):
        return False
    return approval_prefix(command) in approved_prefixes
