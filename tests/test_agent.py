"""Unit tests for the ALIA agent core (offline, full lovelaice stack via MockLLM).

We monkeypatch lovelaice's ``_build_llm`` to a lingo ``MockLLM`` so host ->
Agent -> ReActNative -> ACP -> client all run with no network. Tool calls are
exercised end to end (real read/bash execution against tmp paths), so the
approval gate is genuinely tested.
"""

import lovelaice.agent.agent as agent_mod
from lingo.llm import Message, ToolCall
from lingo.mock import MockLLM

from alia.agent import AliaAgent
from alia.host import ALIA_SYSTEM_PROMPT, DEFAULT_MODEL, create_alia_agent


def _patch_llm(monkeypatch, responses):
    monkeypatch.setattr(agent_mod, "_build_llm", lambda cfg: MockLLM(responses=list(responses)))


def _toolcall(name, **args):
    return Message(role="assistant", content="",
                   tool_calls=[ToolCall(id="c1", name=name, arguments=args)])


class _Spy:
    """Approval handler stub returning "deny" | "once" | "session"."""

    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        return self.decision


# ---- plain chat ---------------------------------------------------------

async def test_chat_returns_reply_through_lovelaice(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, ["Hola, soy ALIA."])
    reply = await AliaAgent(session_path=tmp_path / "s.jsonl").chat("hola")
    assert reply == "Hola, soy ALIA."


async def test_session_persists_to_jsonl(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, ["listo"])
    sp = tmp_path / "sessions" / "s.jsonl"
    await AliaAgent(session_path=sp).chat("hola")
    assert sp.exists()


# ---- the approval gate --------------------------------------------------

async def test_read_is_not_gated(monkeypatch, tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("hello from disk")
    _patch_llm(monkeypatch, [_toolcall("read", path=str(target)), "done"])
    spy = _Spy("once")
    agent = AliaAgent(session_path=tmp_path / "s.jsonl", approval_handler=spy)
    await agent.chat("read it")
    assert spy.calls == []  # read auto-allowed; approval never asked


async def test_safe_bash_auto_runs_without_asking(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, [_toolcall("bash", command="ls -la /tmp"), "done"])
    spy = _Spy("deny")  # would block — but a safe command must not even ask
    agent = AliaAgent(session_path=tmp_path / "s.jsonl", approval_handler=spy)
    await agent.chat("list tmp")
    assert spy.calls == []  # allowlisted -> ran without prompting


async def test_unsafe_bash_runs_when_approved_once(monkeypatch, tmp_path):
    marker = tmp_path / "ran.txt"
    _patch_llm(monkeypatch, [_toolcall("bash", command=f"touch {marker}"), "done"])
    spy = _Spy("once")
    agent = AliaAgent(session_path=tmp_path / "s.jsonl", approval_handler=spy)
    await agent.chat("touch the marker")
    assert spy.calls == [("bash", {"command": f"touch {marker}"})]
    assert marker.exists()


async def test_unsafe_bash_blocked_when_denied(monkeypatch, tmp_path):
    marker = tmp_path / "ran.txt"
    _patch_llm(monkeypatch, [_toolcall("bash", command=f"touch {marker}"), "ok, won't"])
    spy = _Spy("deny")
    agent = AliaAgent(session_path=tmp_path / "s.jsonl", approval_handler=spy)
    await agent.chat("touch the marker")
    assert not marker.exists()  # denied -> never ran


async def test_session_approval_remembers_prefix(monkeypatch, tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    _patch_llm(monkeypatch, [
        _toolcall("bash", command=f"touch {a}"), "first",
        _toolcall("bash", command=f"touch {b}"), "second",
    ])
    spy = _Spy("session")
    agent = AliaAgent(session_path=tmp_path / "s.jsonl", approval_handler=spy)
    await agent.chat("touch a")   # asks once, approves "touch" for the session
    await agent.chat("touch b")   # same prefix -> must NOT ask again
    assert len(spy.calls) == 1
    assert a.exists() and b.exists()
    assert "touch" in agent.approved_prefixes


async def test_tool_events_surface_to_on_event(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, [_toolcall("bash", command="ls /tmp"), "done"])
    events: list[str] = []
    agent = AliaAgent(
        session_path=tmp_path / "s.jsonl",
        approval_handler=_Spy("deny"),
        on_event=lambda kind, params: events.append(kind),
    )
    await agent.chat("go")
    assert "tool_call" in events and "tool_call_update" in events


# ---- host wiring --------------------------------------------------------

def test_host_wires_persona_and_two_tools(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, [])
    agent = create_alia_agent(session_path=tmp_path / "s.jsonl")
    assert agent.config.system_prompt == ALIA_SYSTEM_PROMPT
    assert agent.config.model == DEFAULT_MODEL
    assert len(agent.harness.tools.lingo_tools()) == 2  # read + bash


def test_construction_survives_missing_api_key(monkeypatch, tmp_path):
    for var in ("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY"):
        monkeypatch.delenv(var, raising=False)
    create_alia_agent(session_path=tmp_path / "s.jsonl")
