# ALIA

**ALIA** — the cognitive partner of the AI-n-Box desktop. A native GNOME agent
you summon with a key, backed by the [lingo](https://github.com/apiad/lovelaice)
engine that sits under `lovelaice`.

This repo is the **standalone** slice: ALIA installs and runs on any recent
GNOME, independent of AI-n-Box OS (where she'll later be baked in and pre-wired
to the local Ollama daemon).

> Vision: `vault/Atlas/Architecture/2026-06-25-alia-cognitive-partner-vision.md`
> in the Workspace.

## What works today (v0.1 — chat-only slice)

- A borderless GNOME HUD: transcript + input. **Enter** sends, **Esc** hides.
- A resident single-instance app — pressing the shortcut again toggles the HUD;
  the agent stays alive in the background.
- Replies stream token-by-token, in the user's language, with ALIA's persona.
- Model-agnostic via the engine: defaults to **Haiku over OpenRouter**
  (`anthropic/claude-haiku-4.5`), points anywhere OpenAI-compatible.

**Not yet:** no tools — she can talk and think, but can't act on the system
(open apps, read files, run commands, see the screen). She says so when asked.

## Requirements

- GNOME with **GTK 4** and its Python bindings (`python3-gobject` / PyGObject —
  from your distro, not pip).
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
make shortcut                 # binds <Super>a → ALIA
BINDING='<Super>space' make shortcut   # or pick your own
```

(The bare Super/Windows key is reserved by GNOME for the Activities overview;
cleanly rebinding it is a follow-up. `<Super>a` is the default.)

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
