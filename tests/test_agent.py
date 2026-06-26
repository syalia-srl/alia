"""Unit tests for the ALIA agent core.

ALIA runs on lovelaice's ACP runtime. We monkeypatch lovelaice's
``_build_llm`` to a lingo ``MockLLM`` so the whole stack (host -> Agent ->
ReActNative -> ACP server -> client) runs offline with no network.
"""

import lovelaice.agent.agent as agent_mod
from lingo.mock import MockLLM

from alia.agent import AliaAgent
from alia.host import ALIA_SYSTEM_PROMPT, DEFAULT_MODEL, create_alia_agent


def _patch_llm(monkeypatch, responses):
    monkeypatch.setattr(agent_mod, "_build_llm", lambda cfg: MockLLM(responses=list(responses)))


async def test_chat_returns_reply_through_lovelaice(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, ["Hola, soy ALIA."])
    agent = AliaAgent(session_path=tmp_path / "s.jsonl")
    reply = await agent.chat("hola")
    assert reply == "Hola, soy ALIA."


async def test_chat_streams_finalized_chunk(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, ["uno dos tres"])
    agent = AliaAgent(session_path=tmp_path / "s.jsonl")
    chunks: list[str] = []
    reply = await agent.chat("cuenta", on_chunk=chunks.append)
    assert "".join(chunks) == "uno dos tres"
    assert reply == "uno dos tres"


async def test_session_persists_to_jsonl(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, ["listo"])
    sp = tmp_path / "sessions" / "s.jsonl"
    agent = AliaAgent(session_path=sp)
    await agent.chat("hola")
    assert sp.exists(), "session JSONL should be written under the agent's store"


def test_host_uses_alia_persona_and_no_tools(monkeypatch, tmp_path):
    _patch_llm(monkeypatch, [])  # no LLM call — just construction
    agent = create_alia_agent(session_path=tmp_path / "s.jsonl")
    assert agent.config.system_prompt == ALIA_SYSTEM_PROMPT
    assert agent.config.model == DEFAULT_MODEL
    assert agent.harness.tools.lingo_tools() == []  # chat-only slice


def test_construction_survives_missing_api_key(monkeypatch, tmp_path):
    for var in ("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # Must not raise: the app builds the agent at startup before any key check.
    create_alia_agent(session_path=tmp_path / "s.jsonl")
