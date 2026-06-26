"""Unit tests for the ALIA agent core, using lingo's MockLLM (no network)."""

from lingo.mock import MockLLM

from alia.agent import AliaAgent, build_llm, DEFAULT_MODEL, DEFAULT_BASE_URL


async def test_replies_with_assistant_message():
    agent = AliaAgent(llm=MockLLM(responses=["Hola, soy ALIA."]))
    reply = await agent.chat("hola")
    assert reply == "Hola, soy ALIA."
    assert agent.lingo.messages[-1].role == "assistant"


async def test_keeps_conversation_history_across_turns():
    agent = AliaAgent(llm=MockLLM(responses=["uno", "dos"]))
    await agent.chat("primero")
    await agent.chat("segundo")
    roles = [m.role for m in agent.lingo.messages]
    # both user turns are retained, in order
    assert roles.count("user") == 2
    assert agent.lingo.messages[-1].content == "dos"


async def test_streams_tokens_to_callback():
    agent = AliaAgent(llm=MockLLM(responses=["uno dos tres"]))
    tokens: list[str] = []
    agent.set_on_token(tokens.append)
    await agent.chat("cuenta")
    assert "".join(tokens).split() == ["uno", "dos", "tres"]


def test_build_llm_defaults_to_haiku_over_openrouter(monkeypatch):
    for var in ("ALIA_MODEL", "MODEL", "ALIA_BASE_URL", "BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ALIA_API_KEY", "test-key")  # so the client constructs
    llm = build_llm()
    assert llm.model == DEFAULT_MODEL
    assert "openrouter.ai" in DEFAULT_BASE_URL  # default wired through build_llm


def test_build_llm_survives_missing_api_key(monkeypatch):
    for var in ("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # Must not raise: the app builds the agent at startup before any key check.
    assert build_llm().model == DEFAULT_MODEL
