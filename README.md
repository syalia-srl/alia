# ALIA

**ALIA** — the cognitive partner of the AI-n-Box desktop. A native GNOME agent
you summon with a key, backed by the [lovelaice](https://github.com/apiad/lovelaice)
agent runtime (sessions, persistence, tools, MCP) over its ACP engine.

This repo is the **standalone** slice: ALIA installs and runs on any recent
GNOME, independent of AI-n-Box OS (where she'll later be baked in and pre-wired
to the local Ollama daemon).

> Vision: `vault/Atlas/Architecture/2026-06-25-alia-cognitive-partner-vision.md`
> in the Workspace.

## What works today (v1.0)

- A borderless GNOME HUD with a **WebKit transcript** — real markdown +
  syntax highlighting (reuses superbot's `marked`/`highlight`), an in-page
  "working…" spinner, and input locked while a turn runs. **Enter** sends,
  **Esc** hides.
- A resident single-instance app — pressing the shortcut again toggles the HUD;
  the agent stays alive in the background.
- **She acts on your machine via the shell**, with you in the loop:
  - `read(path)` — reads any file, **silently** (observation is free).
  - `bash(command)` — runs a shell command. **Well-known read-only commands
    auto-run** (`ls`, `cat`, `df`, `git status`, …); anything else shows an
    inline bar with **Deny / Approve / Permitir «prefix» esta sesión**. Picking
    the session option auto-approves that command *prefix* (e.g. `git push`,
    `npm install`) for the rest of the run. This is how she manages files,
    launches apps, changes GNOME settings, inspects the system, uses git, …
  - **Safety floor:** any command containing shell operators (`;`, `|`, `>`,
    `&&`, `$(…)`) always prompts — a safe lead can't smuggle a dangerous tail.
    Hard red-lines (`sudo`, `rm -rf /` …) are blocked outright. Tool activity is
    shown in the transcript as it happens.
- Conversation persists per session to `~/.alia/sessions/<ts>.jsonl`.
- Model-agnostic via the lovelaice engine: defaults to **Haiku over OpenRouter**
  (`anthropic/claude-haiku-4.5`), points anywhere OpenAI-compatible.

**Not yet:** she can't *see* the screen (no screenshots/vision) or control the
mouse/keyboard/click — those are the next rungs. She says so when asked.

## Requirements

- GNOME with **GTK 4** and its Python bindings (`python3-gobject` / PyGObject —
  from your distro, not pip).
- **WebKitGTK 6.0** for the transcript (`gir1.2-webkit-6.0` on Debian/Ubuntu;
  `webkitgtk6.0` on Fedora).
- Python ≥ 3.13.

## Run

```sh
# 1. configure a key (any OpenAI-compatible endpoint; OpenRouter by default)
export ALIA_API_KEY="sk-or-..."
# optional overrides:
#   export ALIA_MODEL="anthropic/claude-haiku-4.5"
#   export ALIA_BASE_URL="https://openrouter.ai/api/v1"

# 2. build the venv (uses --system-site-packages so GTK is visible) and launch
make run
```

`make run` starts the resident app. To summon it with a key:

```sh
make shortcut                 # binds <Super>i → ALIA
BINDING='<Super>j' make shortcut   # or pick your own free key
```

**Picking a key.** Many obvious combos are already grabbed and will silently do
nothing if you bind a custom shortcut to them: the bare Super/Windows key
(Activities overview), `<Super>space` (ibus input-source switch — an
*independent* grabber, so freeing the WM binding isn't enough), and often F12
(terminal dropdowns). The default is **`<Super>i`** (mnemonic for *IA*). If a
binding seems dead, it's almost certainly already taken — check
`/tmp/alia-launch.log`: the launcher logs every time the shortcut actually
fires, so an empty log means the key never reached ALIA.

## Config

| Env var | Default | Purpose |
|---|---|---|
| `ALIA_API_KEY` / `OPENROUTER_API_KEY` / `API_KEY` | — | API key |
| `ALIA_MODEL` / `MODEL` | `anthropic/claude-haiku-4.5` | model slug |
| `ALIA_BASE_URL` / `BASE_URL` | `https://openrouter.ai/api/v1` | endpoint |

## Develop

```sh
make test     # agent-core unit tests (offline, via lingo's MockLLM)
```

The GTK HUD is smoke-tested manually (`make run`); the agent core is unit-tested.

## Status

Conventions: ships to `main`, vertical-slice-first. See `AGENTS.md`.
