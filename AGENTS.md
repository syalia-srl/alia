# AGENTS.md — alia

You're an AI agent picking up **alia**. This file is the door.

## What it is

**ALIA** — the cognitive partner of the AI-n-Box desktop: a native GNOME agent
surface (HUD summoned by a key) on top of the `lingo` engine. Standalone product
(`syalia-srl/alia`), dev/tested on GNOME, later baked into the `ainbox-os`
`desktop` variant. ALIA is the *persona/product*; `lovelaice`/`lingo` is the
*engine*. She is **not** part of the AInBox app suite and does **not** talk to
superbot/magpie — her store is `$HOME`.

Vision doc (canonical):
`vault/Atlas/Architecture/2026-06-25-alia-cognitive-partner-vision.md`.

## Conventions

- **Ships directly to `main`** — no PR cycle (same as the other SYALIA repos).
- **Vertical-slice-first.** Build the thinnest end-to-end path, then widen.
- Agent core is unit-tested (lingo `MockLLM`, offline); the GTK HUD is
  smoke-tested by hand. Keep tests inline — don't delegate them.

## Layout

    src/alia/agent.py    AliaAgent — thin wrapper over lingo.Lingo + ALIA persona
    src/alia/persona.py  the system prompt that makes the engine feel like ALIA
    src/alia/hud.py      the borderless GTK4 HUD (transcript + entry)
    src/alia/app.py      resident single-instance Gtk.Application + asyncio bridge
    src/alia/__main__.py python -m alia
    scripts/install-shortcut.sh   binds a GNOME key (<Super>a) → ALIA
    tests/test_agent.py  agent-core unit tests
    Makefile             install / test / run / shortcut

## Engine notes

- Built on **`lingo.Lingo`** (the chat core under `lovelaice`), NOT
  `lovelaice.core.Lovelaice` — the latter injects coding-agent env/“YOLO tool”
  framing, wrong for the partner voice. As tools land, revisit.
- `Lingo` runs `system_prompt.format(name=, description=)`, so the persona
  prompt must stay free of stray `{`/`}`.
- Model/endpoint resolve from env (`ALIA_*` → generic → defaults: Haiku over
  OpenRouter).

## Runtime/env gotcha

GTK PyGObject (`gi`) comes from the **system** (distro `python3-gobject`), not
pip — so the venv is built with `--system-site-packages` (see Makefile). A plain
isolated venv won't find `gi`.

## Out of scope (current slice)

Tools / acting on the system, screen perception, the autonomy dial, persistent
`$HOME` memory, baking into ainbox-os. All are in the vision doc as next rungs.
