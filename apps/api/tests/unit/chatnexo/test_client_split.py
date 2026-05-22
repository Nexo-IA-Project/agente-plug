from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.adapters.chatnexo.client import ChatNexoClient


def _mock_settings(
    split_max: int = 400,
    split_min: int = 80,
    delay_per_char: int = 30,
    min_delay: int = 800,
    max_delay: int = 4000,
) -> MagicMock:
    s = MagicMock()
    s.chatnexo_split_max_chars = split_max
    s.chatnexo_split_min_chars = split_min
    s.chatnexo_delay_ms_per_char = delay_per_char
    s.chatnexo_min_delay_ms = min_delay
    s.chatnexo_max_delay_ms = max_delay
    return s


def _make_client() -> tuple[ChatNexoClient, MagicMock]:
    http = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    http.post = AsyncMock(return_value=resp)
    return ChatNexoClient(http=http), http


@pytest.mark.asyncio
async def test_send_message_single_part_one_post_no_sleep():
    """Mensagem curta (sem \\n\\n) → 1 POST, sem sleep."""
    client, http = _make_client()
    with (
        patch("shared.adapters.chatnexo.client.get_settings", return_value=_mock_settings()),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await client.send_message(account_id="a", conversation_id="c", text="Olá!")
    http.post.assert_called_once()
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_two_paragraphs_two_posts_one_sleep():
    """Dois parágrafos → 2 POSTs, 1 sleep (entre partes, não após a última)."""
    client, http = _make_client()
    first = "a" * 85  # 85 chars > min_chars=80
    second = "b" * 85
    text = f"{first}\n\n{second}"
    with (
        patch("shared.adapters.chatnexo.client.get_settings", return_value=_mock_settings()),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await client.send_message(account_id="a", conversation_id="c", text=text)
    assert http.post.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_send_message_delay_capped_at_max():
    """Parágrafo longo → delay limitado pelo max_delay."""
    client, _http = _make_client()
    # 600 chars * 30ms = 18000ms > max_delay=4000ms → sleep deve receber 4.0s
    long_para = "x" * 600
    short_para = "y" * 90
    text = f"{long_para}\n\n{short_para}"
    settings = _mock_settings(
        split_max=700, split_min=80, delay_per_char=30, min_delay=800, max_delay=4000
    )
    with (
        patch("shared.adapters.chatnexo.client.get_settings", return_value=settings),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await client.send_message(account_id="a", conversation_id="c", text=text)
    sleep_seconds = mock_sleep.call_args[0][0]
    assert sleep_seconds == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_send_message_delay_floored_at_min():
    """Parágrafo curto → delay não cai abaixo do min_delay."""
    client, _http = _make_client()
    # 85 chars * 1ms = 85ms < min_delay=800ms → sleep deve receber 0.8s
    first = "a" * 85
    second = "b" * 85
    text = f"{first}\n\n{second}"
    settings = _mock_settings(
        split_max=400, split_min=80, delay_per_char=1, min_delay=800, max_delay=4000
    )
    with (
        patch("shared.adapters.chatnexo.client.get_settings", return_value=settings),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await client.send_message(account_id="a", conversation_id="c", text=text)
    sleep_seconds = mock_sleep.call_args[0][0]
    assert sleep_seconds == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_send_template_not_split():
    """send_template() envia 1 POST independente do conteúdo — não é afetado pelo splitter."""
    client, http = _make_client()
    await client.send_template(
        account_id="a",
        conversation_id="c",
        template_name="welcome",
        variables={"1": "Fulano"},
    )
    http.post.assert_called_once()
