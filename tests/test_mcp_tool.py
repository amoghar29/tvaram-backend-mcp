
import pytest
from conftest import ScriptedBackend, connect
from fastmcp import Client
from fastmcp.exceptions import ToolError
import config
from models import Verdict

ADDRESS = "alice@example.com"
MAX_ATTEMPTS = config.MAX_RETRIES + 1


@pytest.fixture(autouse=True)
def no_backoff_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "BACKOFF_BASE_SECONDS", 0.0)


async def test_tool_is_advertised_with_a_usable_schema(agent: Client) -> None:
    tools = await agent.list_tools()
    assert [tool.name for tool in tools] == ["verify_email"]
    tool = tools[0]
    assert tool.description
    assert tool.inputSchema["properties"]["address"]["type"] == "string"
    assert tool.inputSchema["required"] == ["address"]
    assert tool.outputSchema["properties"]["verdict"]["enum"] == [v.value for v in Verdict]


@pytest.mark.parametrize(
    ("address", "verdict"),
    [
        (ADDRESS, Verdict.VALID),
        ("not-an-email", Verdict.INVALID),
        ("alice@mailinator.com", Verdict.RISKY),
    ],
)
async def test_each_verdict_round_trips_as_structured_content(
    agent: Client, address: str, verdict: Verdict
) -> None:
    result = await agent.call_tool("verify_email", {"address": address})
    assert result.structured_content["address"] == address
    assert result.structured_content["verdict"] == verdict.value
    assert result.structured_content["reason"]


async def test_address_is_returned_normalized(agent: Client) -> None:
    result = await agent.call_tool("verify_email", {"address": "  Alice@Example.COM  "})
    assert result.structured_content["address"] == ADDRESS


async def test_the_retry_budget_is_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ScriptedBackend(*[503] * (MAX_ATTEMPTS + 1))

    async with backend.verifier() as verifier, connect(verifier, monkeypatch) as agent:
        with pytest.raises(ToolError, match="503"):
            await agent.call_tool("verify_email", {"address": ADDRESS})

    assert backend.verify_requests == MAX_ATTEMPTS


async def test_client_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ScriptedBackend(400)

    async with backend.verifier() as verifier, connect(verifier, monkeypatch) as agent:
        with pytest.raises(ToolError, match="400"):
            await agent.call_tool("verify_email", {"address": ADDRESS})
    assert backend.verify_requests == 1


async def test_the_token_is_minted_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ScriptedBackend()

    async with backend.verifier() as verifier, connect(verifier, monkeypatch) as agent:
        await agent.call_tool("verify_email", {"address": ADDRESS})
        await agent.call_tool("verify_email", {"address": "bob@example.com"})

    assert backend.token_requests == 1
    assert backend.verify_requests == 2


async def test_a_rejected_token_is_replaced_once(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ScriptedBackend(401)

    async with backend.verifier() as verifier, connect(verifier, monkeypatch) as agent:
        result = await agent.call_tool("verify_email", {"address": ADDRESS})

    assert result.structured_content["verdict"] == Verdict.VALID
    assert backend.token_requests == 2
