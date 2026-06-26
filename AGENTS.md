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

    src/alia/host.py     create_alia_agent — assembles a lovelaice Agent (persona, tools)
    src/alia/agent.py    AliaAgent — in-process ACP client driving the lovelaice runtime
    src/alia/persona.py  the system prompt (base passed to assemble_system_prompt)
    src/alia/hud.py      the borderless GTK4 HUD (transcript + entry)
    src/alia/app.py      resident single-instance Gtk.Application + asyncio bridge
    src/alia/__main__.py python -m alia
    scripts/install-shortcut.sh   binds a GNOME key (<Super>i) → ALIA
    scripts/alia-launch.sh        logging launcher used by the shortcut
    tests/test_agent.py  agent-core unit tests (offline via MockLLM)
    Makefile             install / test / run / shortcut

## Engine notes

- Built on the **lovelaice agent runtime**, not bare lingo and not the legacy
  `lovelaice.core.Lovelaice`. The chain is:
  `host.create_alia_agent` → `lovelaice.agent.Agent` (ReActNative loop, JSONL
  session) → driven via `AcpServer` + `InProcessAcpClient` (same path
  lovelaice's CLI uses). This gives sessions, persistence, tool dispatch,
  hooks, and MCP for free — we do NOT re-implement an agent loop.
- **Persona** is the `system_prompt` base on `AgentConfig`; lovelaice's
  `assemble_system_prompt` appends tool descriptions. No `Lingo.format()` here,
  so the persona prompt is plain text (brace constraint no longer applies, but
  keep it clean).
- **Streaming:** ACP emits `agent_message_chunk` with the *finalized* assistant
  text (one chunk per turn in VS1), tool calls as their own notifications. The
  HUD shows the chunk when it arrives. Token-level streaming is a later rung.
- **Tools / MCP** wire into `host.create_alia_agent` (currently `tools=[]`).
- Sessions persist to `~/.alia/sessions/<ts>.jsonl` (ALIA's `$HOME` store). The
  beaverdb `ConversationStore` is the richer next layer (pass
  `conversation_store=` to `AcpServer`).
- Model/endpoint resolve from env (`ALIA_*` → generic → defaults: Haiku over
  OpenRouter).

## Runtime/env gotcha

GTK PyGObject (`gi`) comes from the **system** (distro `python3-gobject`), not
pip — so the venv is built with `--system-site-packages` (see Makefile). A plain
isolated venv won't find `gi`.

## Out of scope (current slice)

Tools / acting on the system, screen perception, the autonomy dial, persistent
`$HOME` memory, baking into ainbox-os. All are in the vision doc as next rungs.
