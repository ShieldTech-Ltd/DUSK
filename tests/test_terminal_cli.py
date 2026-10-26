from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from click.testing import CliRunner
from test_terminal_runtime import config_file

from dusk.cli import main


def test_dusk_opens_a_branded_welcome_without_claiming_active_protection() -> None:
    result = CliRunner().invoke(main, [])
    assert result.exit_code == 0
    assert "DUSK" in result.output
    assert "welcome" not in result.output.lower()
    assert "Agent action security" in result.output
    assert "Protection starts when configured operations run through DUSK." in result.output
    assert "dusk doctor" in result.output
    assert "dusk mcp" in result.output


def test_cli_doctor_and_run_use_the_real_runtime(tmp_path: Path) -> None:
    path = config_file(tmp_path)
    runner = CliRunner()
    doctor = runner.invoke(main, ["doctor", "--config", str(path)])
    assert doctor.exit_code == 0
    assert json.loads(doctor.output)["configured_operations"] == 1
    request = str(uuid.uuid4())
    allowed = runner.invoke(
        main, ["run", "write-marker", "--config", str(path), "--request-id", request]
    )
    assert allowed.exit_code == 0
    assert (tmp_path / "effect").exists()
    replay = runner.invoke(
        main, ["run", "write-marker", "--config", str(path), "--request-id", request]
    )
    assert replay.exit_code == 1
    assert json.loads(replay.output)["status"] == "REPLAY_REJECTED"


def test_cli_missing_config_fails_without_echoing_contents(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["doctor", "--config", str(tmp_path / "missing")])
    assert result.exit_code != 0


def test_mcp_subprocess_discovers_executes_blocks_and_rejects_replay(tmp_path: Path) -> None:
    from mcp import Client, StdioServerParameters

    path = config_file(tmp_path)

    async def check() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "dusk", "mcp", "--config", str(path)],
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        )
        async with Client(params) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {"dusk_operations", "dusk_execute"}
            schema = next(tool for tool in tools.tools if tool.name == "dusk_execute").input_schema
            assert set(schema["properties"]) == {"operation", "request_id"}
            request = str(uuid.uuid4())
            result = await client.call_tool(
                "dusk_execute", {"operation": "write-marker", "request_id": request}
            )
            assert not result.is_error
            assert "EXECUTED" in str(result)
            assert (tmp_path / "effect").exists()
            (tmp_path / "effect").unlink()
            replay = await client.call_tool(
                "dusk_execute", {"operation": "write-marker", "request_id": request}
            )
            assert "REPLAY_REJECTED" in str(replay)
            denied = await client.call_tool(
                "dusk_execute", {"operation": "unknown", "request_id": str(uuid.uuid4())}
            )
            assert "BLOCKED" in str(denied)
            assert not (tmp_path / "effect").exists()

    asyncio.run(check())
