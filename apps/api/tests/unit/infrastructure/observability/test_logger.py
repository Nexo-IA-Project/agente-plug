import json

import pytest

from shared.adapters.observability.logger import (
    bind_context,
    configure_logging,
    get_logger,
    reset_context,
)


@pytest.fixture(autouse=True)
def setup_logging() -> None:
    configure_logging(level="INFO")
    reset_context()


def test_log_includes_correlation_id(capsys: pytest.CaptureFixture[str]) -> None:
    bind_context(correlation_id="corr-1", account_id="acct-1")
    log = get_logger("test")
    log.info("hello", extra_field="x")
    captured = capsys.readouterr().out.strip()
    assert captured, "expected output"
    parsed = json.loads(captured.splitlines()[-1])
    assert parsed["correlation_id"] == "corr-1"
    assert parsed["account_id"] == "acct-1"
    assert parsed["extra_field"] == "x"
    assert parsed["event"] == "hello"
