# Message Splitting + Webhook Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o `ChatNexoClient.send_message()` quebrar textos longos em partes menores com delay dinâmico entre envios, e criar um script local para disparar webhooks Hubla sem depender da plataforma.

**Architecture:** A lógica de split fica em `message_splitter.py` (função pura, zero deps externas, testável isoladamente). O `send_message()` em `client.py` chama o splitter e dorme entre partes usando `asyncio.sleep`. O webhook simulator (`scripts/webhook-sim/`) é um script Python standalone que lê `.env.local` e faz POST no endpoint local com o token correto no header.

**Tech Stack:** Python 3.11, httpx, pydantic-settings, pytest + pytest-asyncio, python-dotenv (apenas no script de teste)

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `apps/api/src/shared/adapters/chatnexo/message_splitter.py` | CRIAR | Função pura `split_message()` — sem deps externas |
| `apps/api/src/shared/adapters/chatnexo/client.py` | MODIFICAR | `send_message()` usa splitter + delay |
| `apps/api/src/shared/config/settings.py` | MODIFICAR | 5 novas variáveis de split/delay com defaults |
| `.env.example` | MODIFICAR | Documenta novas variáveis |
| `apps/api/tests/unit/chatnexo/test_message_splitter.py` | CRIAR | Testes unitários do splitter |
| `apps/api/tests/unit/chatnexo/test_client_split.py` | CRIAR | Testes de `send_message()` com mock HTTP |
| `scripts/webhook-sim/fire_webhook.py` | CRIAR | Script de disparo de webhook |
| `scripts/webhook-sim/payloads/hubla_subscription_activated.json` | CRIAR | Payload de compra simples |
| `scripts/webhook-sim/payloads/hubla_subscription_activated_multi.json` | CRIAR | Payload multi-produto |
| `scripts/webhook-sim/README.md` | CRIAR | Instruções de uso |
| `apps/api/tests/unit/scripts/__init__.py` | CRIAR | Torna pasta de testes importável |
| `apps/api/tests/unit/scripts/test_fire_webhook.py` | CRIAR | Testes de substituição de placeholders |

---

## Task 1: `message_splitter.py` — função pura com TDD

**Files:**
- Create: `apps/api/tests/unit/chatnexo/test_message_splitter.py`
- Create: `apps/api/src/shared/adapters/chatnexo/message_splitter.py`

- [ ] **Step 1: Criar o arquivo de teste**

Crie `apps/api/tests/unit/chatnexo/test_message_splitter.py` com o conteúdo abaixo. Ainda não crie o módulo — o teste deve falhar com `ModuleNotFoundError`.

```python
from __future__ import annotations

import pytest

from shared.adapters.chatnexo.message_splitter import split_message


def test_short_message_no_double_newline_returns_single_part():
    """Mensagem sem \\n\\n retorna sempre uma só parte, qualquer tamanho."""
    result = split_message("Olá! Como posso ajudar você hoje?")
    assert result == ["Olá! Como posso ajudar você hoje?"]


def test_two_paragraphs_returns_two_parts():
    text = "Primeiro parágrafo de teste.\n\nSegundo parágrafo de teste."
    result = split_message(text)
    assert result == ["Primeiro parágrafo de teste.", "Segundo parágrafo de teste."]


def test_long_paragraph_split_by_sentence_respects_max_chars():
    # 12 sentenças de ~36 chars cada → ~432 chars, excede max_chars=200
    sentence = "Esta é uma sentença longa. "
    text = (sentence * 12).strip()
    result = split_message(text, max_chars=200)
    assert len(result) > 1
    for part in result:
        assert len(part) <= 200


def test_short_parts_below_min_chars_discarded():
    # "ok" tem 2 chars < min_chars=80, deve ser descartado
    long_part = "a" * 85  # 85 chars, passa o filtro
    text = f"{long_part}\n\nok"
    result = split_message(text, min_chars=80)
    assert len(result) == 1
    assert result[0] == long_part


def test_whitespace_only_returns_empty_list():
    assert split_message("   \n\n   ") == []
    assert split_message("") == []
    assert split_message("\n\n\n") == []


def test_all_parts_too_short_returns_original_as_fallback():
    # Ambos os parágrafos < min_chars → retorna texto original
    text = "ab\n\ncd"
    result = split_message(text, min_chars=80)
    assert result == ["ab\n\ncd"]


def test_three_paragraphs():
    text = "Parte um.\n\nParte dois.\n\nParte três."
    result = split_message(text)
    assert result == ["Parte um.", "Parte dois.", "Parte três."]
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd apps/api && uv run pytest tests/unit/chatnexo/test_message_splitter.py -v
```

Esperado: `FAILED` ou `ERROR` com `ModuleNotFoundError: No module named 'shared.adapters.chatnexo.message_splitter'`

- [ ] **Step 3: Criar `message_splitter.py`**

Crie `apps/api/src/shared/adapters/chatnexo/message_splitter.py`:

```python
from __future__ import annotations

import re


def split_message(text: str, max_chars: int = 400, min_chars: int = 80) -> list[str]:
    """Quebra texto em partes menores para envio humanizado via WhatsApp.

    Estratégia:
    1. Sem \\n\\n → retorna [text] inteiro
    2. Com \\n\\n → quebra por parágrafo
    3. Parágrafo > max_chars → subdivide por sentença
    4. Parte < min_chars → descartada
    5. Se todos descartados → retorna [text] original (fallback)
    """
    stripped = text.strip()
    if not stripped:
        return []

    if "\n\n" not in stripped:
        return [stripped]

    paragraphs = [p.strip() for p in stripped.split("\n\n") if p.strip()]

    parts: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            parts.append(para)
        else:
            parts.extend(_split_by_sentence(para, max_chars))

    filtered = [p for p in parts if len(p) >= min_chars]
    return filtered if filtered else [stripped]


def _split_by_sentence(text: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.?!])\s+", text)
    groups: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        candidate = (current + " " + sentence).strip() if current else sentence
        if current and len(candidate) > max_chars:
            groups.append(current.strip())
            current = sentence
        else:
            current = candidate
    if current:
        groups.append(current.strip())
    return groups
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```bash
cd apps/api && uv run pytest tests/unit/chatnexo/test_message_splitter.py -v
```

Esperado: todos os 7 testes com `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/chatnexo/message_splitter.py \
        apps/api/tests/unit/chatnexo/test_message_splitter.py
git commit -m "feat(chatnexo): message_splitter com testes"
```

---

## Task 2: Variáveis de configuração no `settings.py`

**Files:**
- Modify: `apps/api/src/shared/config/settings.py`
- Modify: `.env.example`

- [ ] **Step 1: Adicionar os campos em `settings.py`**

Abra `apps/api/src/shared/config/settings.py`. Após a linha `chatnexo_api_key: str` (linha 29), adicione o bloco abaixo:

```python
    # ChatNexo — message splitting e delay humanizado
    chatnexo_split_max_chars: int = Field(default=400, ge=50)
    chatnexo_split_min_chars: int = Field(default=80, ge=10)
    chatnexo_delay_ms_per_char: int = Field(default=30, ge=0)
    chatnexo_min_delay_ms: int = Field(default=800, ge=0)
    chatnexo_max_delay_ms: int = Field(default=4000, ge=0)
```

- [ ] **Step 2: Adicionar ao `.env.example`**

Abra `.env.example` e adicione após a linha `CHATNEXO_API_KEY=`:

```
# ChatNexo — message splitting (valores são os defaults, ajuste conforme necessário)
CHATNEXO_SPLIT_MAX_CHARS=400
CHATNEXO_SPLIT_MIN_CHARS=80
CHATNEXO_DELAY_MS_PER_CHAR=30
CHATNEXO_MIN_DELAY_MS=800
CHATNEXO_MAX_DELAY_MS=4000
```

- [ ] **Step 3: Verificar que os testes existentes ainda passam**

```bash
cd apps/api && uv run pytest tests/unit/ -v --tb=short -q
```

Esperado: todos os testes existentes com `PASSED`, sem erros de importação.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/config/settings.py .env.example
git commit -m "feat(settings): variáveis de split e delay do chatnexo"
```

---

## Task 3: Modificar `send_message()` para usar split + delay

**Files:**
- Create: `apps/api/tests/unit/chatnexo/test_client_split.py`
- Modify: `apps/api/src/shared/adapters/chatnexo/client.py`

- [ ] **Step 1: Criar o arquivo de teste**

Crie `apps/api/tests/unit/chatnexo/test_client_split.py`:

```python
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
    with patch("shared.adapters.chatnexo.client.get_settings", return_value=_mock_settings()):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.send_message(account_id="a", conversation_id="c", text="Olá!")
    http.post.assert_called_once()
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_two_paragraphs_two_posts_one_sleep():
    """Dois parágrafos → 2 POSTs, 1 sleep (entre partes, não após a última)."""
    client, http = _make_client()
    first = "a" * 85   # 85 chars > min_chars=80
    second = "b" * 85
    text = f"{first}\n\n{second}"
    with patch("shared.adapters.chatnexo.client.get_settings", return_value=_mock_settings()):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.send_message(account_id="a", conversation_id="c", text=text)
    assert http.post.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_send_message_delay_capped_at_max():
    """Parágrafo muito longo → delay limitado pelo max_delay."""
    client, http = _make_client()
    # 600 chars * 30ms = 18000ms > max_delay=4000ms → sleep deve receber 4.0s
    long_para = "x" * 600
    short_para = "y" * 90
    text = f"{long_para}\n\n{short_para}"
    settings = _mock_settings(split_max=700, split_min=80, delay_per_char=30, min_delay=800, max_delay=4000)
    with patch("shared.adapters.chatnexo.client.get_settings", return_value=settings):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.send_message(account_id="a", conversation_id="c", text=text)
    sleep_seconds = mock_sleep.call_args[0][0]
    assert sleep_seconds == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_send_message_delay_floored_at_min():
    """Parágrafo curto → delay não cai abaixo do min_delay."""
    client, http = _make_client()
    # 85 chars * 1ms = 85ms < min_delay=800ms → sleep deve receber 0.8s
    first = "a" * 85
    second = "b" * 85
    text = f"{first}\n\n{second}"
    settings = _mock_settings(split_max=400, split_min=80, delay_per_char=1, min_delay=800, max_delay=4000)
    with patch("shared.adapters.chatnexo.client.get_settings", return_value=settings):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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
```

- [ ] **Step 2: Rodar para confirmar que falha**

```bash
cd apps/api && uv run pytest tests/unit/chatnexo/test_client_split.py -v
```

Esperado: os 4 primeiros testes falham (comportamento atual envia 1 POST sempre). `test_send_template_not_split` passa.

- [ ] **Step 3: Modificar `send_message()` em `client.py`**

Abra `apps/api/src/shared/adapters/chatnexo/client.py`. Adicione `import asyncio` no topo junto com os outros imports, e substitua o método `send_message()`:

**Adicione no topo (após `import httpx`):**
```python
import asyncio
```

**Substitua `send_message()`** (era 3 linhas, passa a ser):

```python
    async def send_message(self, *, account_id: str, conversation_id: str, text: str) -> None:
        from shared.adapters.chatnexo.message_splitter import split_message

        s = get_settings()
        parts = split_message(
            text,
            max_chars=s.chatnexo_split_max_chars,
            min_chars=s.chatnexo_split_min_chars,
        )

        for i, part in enumerate(parts):
            await self._post(
                f"/accounts/{account_id}/conversations/{conversation_id}/messages",
                json={"type": "text", "content": part},
            )
            if i < len(parts) - 1:
                delay_ms = len(part) * s.chatnexo_delay_ms_per_char
                delay_ms = max(s.chatnexo_min_delay_ms, min(delay_ms, s.chatnexo_max_delay_ms))
                await asyncio.sleep(delay_ms / 1000)
```

- [ ] **Step 4: Rodar os testes do client**

```bash
cd apps/api && uv run pytest tests/unit/chatnexo/test_client_split.py -v
```

Esperado: todos os 5 testes `PASSED`.

- [ ] **Step 5: Rodar todos os testes unitários para checar regressão**

```bash
cd apps/api && uv run pytest tests/unit/ -v --tb=short -q
```

Esperado: todos os testes existentes continuam `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/adapters/chatnexo/client.py \
        apps/api/tests/unit/chatnexo/test_client_split.py
git commit -m "feat(chatnexo): send_message com split de parágrafos e delay dinâmico"
```

---

## Task 4: Webhook Simulator

**Files:**
- Create: `scripts/webhook-sim/fire_webhook.py`
- Create: `scripts/webhook-sim/payloads/hubla_subscription_activated.json`
- Create: `scripts/webhook-sim/payloads/hubla_subscription_activated_multi.json`
- Create: `scripts/webhook-sim/README.md`
- Create: `apps/api/tests/unit/scripts/__init__.py`
- Create: `apps/api/tests/unit/scripts/test_fire_webhook.py`

- [ ] **Step 1: Criar os payloads JSON**

Crie `scripts/webhook-sim/payloads/hubla_subscription_activated.json`:

```json
{
  "type": "subscription.activated",
  "version": "2.0.0",
  "event": {
    "product": {
      "id": "{{HUBLA_PRODUCT_ID}}",
      "name": "Produto Teste NexoIA"
    },
    "products": [
      {
        "id": "{{HUBLA_PRODUCT_ID}}",
        "name": "Produto Teste NexoIA",
        "offers": []
      }
    ],
    "subscription": {
      "id": "{{SUBSCRIPTION_ID}}",
      "payer": {
        "firstName": "Teste",
        "lastName": "NexoIA",
        "document": "00000000000",
        "email": "teste@nexoia.com.br",
        "phone": "{{PHONE}}"
      },
      "activatedAt": "{{TIMESTAMP_ISO}}",
      "paymentMethod": "credit_card",
      "type": "one_time",
      "status": "active"
    },
    "user": {
      "id": "test-user-id",
      "email": "teste@nexoia.com.br",
      "phone": "{{PHONE}}"
    }
  }
}
```

Crie `scripts/webhook-sim/payloads/hubla_subscription_activated_multi.json`:

```json
{
  "type": "subscription.activated",
  "version": "2.0.0",
  "event": {
    "product": {
      "id": "{{HUBLA_PRODUCT_ID}}",
      "name": "Produto Teste A"
    },
    "products": [
      {
        "id": "{{HUBLA_PRODUCT_ID}}",
        "name": "Produto Teste A",
        "offers": []
      },
      {
        "id": "{{HUBLA_PRODUCT_ID_2}}",
        "name": "Produto Teste B",
        "offers": []
      }
    ],
    "subscription": {
      "id": "{{SUBSCRIPTION_ID}}",
      "payer": {
        "firstName": "Teste",
        "lastName": "Multi",
        "document": "00000000000",
        "email": "teste@nexoia.com.br",
        "phone": "{{PHONE}}"
      },
      "activatedAt": "{{TIMESTAMP_ISO}}",
      "paymentMethod": "credit_card",
      "type": "one_time",
      "status": "active"
    },
    "user": {
      "id": "test-user-id",
      "email": "teste@nexoia.com.br",
      "phone": "{{PHONE}}"
    }
  }
}
```

- [ ] **Step 2: Criar `fire_webhook.py`**

Crie `scripts/webhook-sim/fire_webhook.py`:

```python
#!/usr/bin/env python3
"""Dispara um webhook Hubla simulado para o endpoint local /webhook/purchase.

Uso:
    uv run python scripts/webhook-sim/fire_webhook.py
    uv run python scripts/webhook-sim/fire_webhook.py --phone +5511999999999
    uv run python scripts/webhook-sim/fire_webhook.py --payload hubla_subscription_activated_multi
    uv run python scripts/webhook-sim/fire_webhook.py --url http://staging.example.com

Requer em .env.local:
    HUBLA_WEBHOOK_SECRET=...
    TEST_CONTACT_PHONE=+55...
    TEST_HUBLA_PRODUCT_ID=...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_REPO_ROOT = Path(__file__).parent.parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO_ROOT / ".env.local", override=True)
    except ImportError:
        pass  # python-dotenv não instalado — variáveis devem estar no ambiente


def _load_payload(name: str) -> dict:
    payloads_dir = Path(__file__).parent / "payloads"
    path = payloads_dir / f"{name}.json"
    if not path.exists():
        available = [p.stem for p in payloads_dir.glob("*.json")]
        print(f"Payload '{name}' não encontrado. Disponíveis: {available}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def _fill_placeholders(payload: dict, *, phone: str, product_id: str, product_id_2: str = "") -> dict:
    text = json.dumps(payload)
    now = datetime.now(UTC)
    text = text.replace("{{PHONE}}", phone)
    text = text.replace("{{HUBLA_PRODUCT_ID_2}}", product_id_2 or product_id)
    text = text.replace("{{HUBLA_PRODUCT_ID}}", product_id)
    text = text.replace("{{SUBSCRIPTION_ID}}", str(uuid4()))
    text = text.replace("{{TIMESTAMP_ISO}}", now.isoformat().replace("+00:00", "Z"))
    return json.loads(text)


def main() -> None:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Dispara webhook Hubla de teste")
    parser.add_argument("--payload", default="hubla_subscription_activated",
                        help="Nome do arquivo de payload (sem .json)")
    parser.add_argument("--phone", default=os.getenv("TEST_CONTACT_PHONE", ""),
                        help="Telefone do contato (ex: +5511999999999)")
    parser.add_argument("--product-id", default=os.getenv("TEST_HUBLA_PRODUCT_ID", ""),
                        help="ID do produto na Hubla")
    parser.add_argument("--url", default=os.getenv("API_URL", "http://localhost:8000"),
                        help="URL base da API")
    args = parser.parse_args()

    if not args.phone:
        print("Erro: defina TEST_CONTACT_PHONE no .env.local ou use --phone", file=sys.stderr)
        sys.exit(1)
    if not args.product_id:
        print("Erro: defina TEST_HUBLA_PRODUCT_ID no .env.local ou use --product-id", file=sys.stderr)
        sys.exit(1)

    token = os.getenv("HUBLA_WEBHOOK_SECRET", "")
    if not token:
        print("Erro: HUBLA_WEBHOOK_SECRET não encontrado no .env.local", file=sys.stderr)
        sys.exit(1)

    raw_payload = _load_payload(args.payload)
    payload = _fill_placeholders(raw_payload, phone=args.phone, product_id=args.product_id)

    try:
        import httpx
    except ImportError:
        print("Erro: httpx não instalado. Execute: uv add httpx", file=sys.stderr)
        sys.exit(1)

    url = f"{args.url.rstrip('/')}/webhook/purchase"
    print(f"→ POST {url}")
    print(f"  payload: {args.payload} | telefone: {args.phone} | produto: {args.product_id}")

    response = httpx.post(url, json=payload, headers={"x-hubla-token": token})
    print(f"  status: {response.status_code}")
    print(f"  body:   {response.text}")

    if response.status_code not in (200, 202):
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Criar `README.md`**

Crie `scripts/webhook-sim/README.md`:

```markdown
# Webhook Simulator

Dispara webhooks Hubla para o endpoint local sem depender da plataforma Hubla.

## Pré-requisitos

- API rodando em `http://localhost:8000` (ou defina `API_URL` no `.env.local`)
- Worker rodando (para processar o job de compra)

## Configuração

Adicione ao `.env.local` na raiz do repositório:

```
TEST_CONTACT_PHONE=+5511999999999
TEST_HUBLA_PRODUCT_ID=QaIlGtff9tlU94JjDKSq
```

`TEST_HUBLA_PRODUCT_ID` deve corresponder ao `hubla_id` de um `Course` cadastrado no painel.

## Uso

```bash
# Disparo simples (usa TEST_CONTACT_PHONE e TEST_HUBLA_PRODUCT_ID do .env.local)
uv run python scripts/webhook-sim/fire_webhook.py

# Sobrescrever telefone
uv run python scripts/webhook-sim/fire_webhook.py --phone +5511988887777

# Payload multi-produto
uv run python scripts/webhook-sim/fire_webhook.py --payload hubla_subscription_activated_multi

# Apontar para outra instância
uv run python scripts/webhook-sim/fire_webhook.py --url http://staging.example.com
```

## Payloads disponíveis

| Arquivo | Descrição |
|---|---|
| `hubla_subscription_activated.json` | Compra simples — 1 produto |
| `hubla_subscription_activated_multi.json` | Compra com 2 produtos no array `products[]` |

## O que acontece ao disparar

1. Script lê `HUBLA_WEBHOOK_SECRET` do `.env.local`
2. Envia `POST /webhook/purchase` com `x-hubla-token: {secret}`
3. API enfileira job `purchase` no worker
4. Worker processa: cria/atualiza contato, abre conversa no ChatNexo, enrolla em flows do curso
5. Mensagem de boas-vindas é enviada para o `TEST_CONTACT_PHONE` via WhatsApp
```

- [ ] **Step 4: Criar os testes do script**

Crie `apps/api/tests/unit/scripts/__init__.py` (arquivo vazio):
```
```

Crie `apps/api/tests/unit/scripts/test_fire_webhook.py`:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Adiciona o diretório do script ao path para poder importar fire_webhook
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "scripts" / "webhook-sim"))

from fire_webhook import _fill_placeholders, _load_payload  # noqa: E402


def test_fill_placeholders_replaces_phone():
    payload = {"event": {"subscription": {"payer": {"phone": "{{PHONE}}"}}}}
    result = _fill_placeholders(payload, phone="+5511999999999", product_id="prod123")
    assert result["event"]["subscription"]["payer"]["phone"] == "+5511999999999"


def test_fill_placeholders_replaces_product_id():
    payload = {"event": {"product": {"id": "{{HUBLA_PRODUCT_ID}}"}}}
    result = _fill_placeholders(payload, phone="+5511999999999", product_id="abc123")
    assert result["event"]["product"]["id"] == "abc123"


def test_fill_placeholders_subscription_id_is_unique():
    payload = {"event": {"subscription": {"id": "{{SUBSCRIPTION_ID}}"}}}
    result1 = _fill_placeholders(payload, phone="+55", product_id="x")
    result2 = _fill_placeholders(payload, phone="+55", product_id="x")
    assert result1["event"]["subscription"]["id"] != result2["event"]["subscription"]["id"]


def test_fill_placeholders_timestamp_iso_is_valid():
    from datetime import datetime
    payload = {"activatedAt": "{{TIMESTAMP_ISO}}"}
    result = _fill_placeholders(payload, phone="+55", product_id="x")
    # Deve ser parseável como ISO datetime
    dt = datetime.fromisoformat(result["activatedAt"].replace("Z", "+00:00"))
    assert dt is not None


def test_load_payload_returns_dict():
    payload = _load_payload("hubla_subscription_activated")
    assert payload["type"] == "subscription.activated"
    assert "event" in payload


def test_load_payload_multi_returns_two_products():
    payload = _load_payload("hubla_subscription_activated_multi")
    assert len(payload["event"]["products"]) == 2
```

- [ ] **Step 5: Rodar os testes do script**

```bash
cd apps/api && uv run pytest tests/unit/scripts/test_fire_webhook.py -v
```

Esperado: todos os 6 testes `PASSED`.

- [ ] **Step 6: Rodar toda a suite unitária**

```bash
cd apps/api && uv run pytest tests/unit/ -v --tb=short -q
```

Esperado: todos os testes passando, incluindo os novos.

- [ ] **Step 7: Commit final**

```bash
git add scripts/ apps/api/tests/unit/scripts/
git commit -m "feat(scripts): webhook simulator para testes locais de disparo Hubla"
```

---

## Task 5: Adicionar `TEST_CONTACT_PHONE` e `TEST_HUBLA_PRODUCT_ID` ao `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Adicionar variáveis de teste ao `.env.example`**

Abra `.env.example` e adicione ao final:

```
# Webhook Simulator (scripts/webhook-sim/)
TEST_CONTACT_PHONE=+5511999999999
TEST_HUBLA_PRODUCT_ID=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: documenta variáveis do webhook simulator no .env.example"
```

---

## Teste Manual Final

Após implementar todas as tasks:

- [ ] Certifique-se de que `TEST_CONTACT_PHONE` e `TEST_HUBLA_PRODUCT_ID` estão no `.env.local`
- [ ] Suba a infra: `docker compose up postgres redis`
- [ ] Suba a API: `cd apps/api && uv run uvicorn main:app --reload`
- [ ] Suba o worker: `cd apps/api && uv run python -m worker`
- [ ] Dispare o webhook: `uv run python scripts/webhook-sim/fire_webhook.py`
- [ ] Verifique que o WhatsApp recebeu a mensagem de boas-vindas no número `TEST_CONTACT_PHONE`
- [ ] Envie uma resposta via WhatsApp e verifique que a IA responde com mensagens quebradas em partes

---

## Spec de referência

`docs/superpowers/specs/2026-05-22-message-split-webhook-sim-design.md`
