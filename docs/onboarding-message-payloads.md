# Payloads de envio de mensagem (onboarding / follow-up)

> Referência extraída do código (`ChatNexoClient` + `DispatchOnboardingStep` + `VariableResolver`).
> **Importante:** as mensagens ao usuário final do WhatsApp **NÃO** são enviadas direto na Graph API da Meta. Elas passam pelo **ChatNexo** (fork do Chatwoot), que decide entre enviar texto livre (dentro da janela de 24h) ou disparar o template real na Meta (fora da janela). O `MetaTemplateClient` (Graph API) é usado **só** para criar/listar/editar templates e fazer upload de mídia — não para enviar.

---

## 1. Transporte comum (endpoint + auth)

Todo envio é um `POST` para o ChatNexo:

```
POST {CHATNEXO_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages
Headers:
  api_access_token: {CHATNEXO_API_KEY}
  Content-Type: application/json
```

- `account_id` — id da conta no ChatNexo (no dispatch de onboarding o default é `1`).
- `conversation_id` — id da conversa no ChatNexo.
- Retries: 3 tentativas com backoff exponencial (em `HTTPStatusError`/`TransportError`).
- `401/403` → erro explícito de credencial.

---

## 2. Mensagem normal (texto livre)

Usada quando o step tem `message_text` (texto livre, sem template). O texto é **dividido em partes** (`message_splitter`) — cada parte é um POST separado, com um pequeno delay entre elas (simula digitação). **Um POST por parte:**

```json
{
  "type": "text",
  "content": "Olá! Tudo certo com seu acesso ao curso?"
}
```

> Se o texto for longo, gera N payloads como acima (um por fatia). Mensagens curtas = 1 único POST.

---

## 3. Template (sem mídia) — variáveis NOMEADAS (`NAMED`)

Usada quando o step aponta para um `meta_template_name`. O cliente envia **dois campos**:
- `content`: o body do template **já renderizado localmente** (as `{{var}}` substituídas) — é o que o ChatNexo manda como texto livre se estiver dentro da janela de 24h.
- `template_params`: metadados para o ChatNexo reenviar como template real via Meta fora da janela.

Exemplo — template `boas_vindas` com body `Olá {{customer_name}}, bem-vindo ao {{product_name}}!`:

```json
{
  "content": "Olá João, bem-vindo ao Curso de Tráfego!",
  "template_params": {
    "name": "boas_vindas",
    "language": "pt_BR",
    "parameter_format": "NAMED",
    "processed_params": {
      "customer_name": "João",
      "product_name": "Curso de Tráfego"
    }
  }
}
```

### 3b. Variante POSITIONAL (`{{1}}`, `{{2}}`)

Se o template usa placeholders posicionais, `parameter_format` é `"POSITIONAL"` e `processed_params` vira um dict com chaves numéricas **em ordem alfabética dos nomes originais**:

```json
{
  "content": "Olá João, bem-vindo ao Curso de Tráfego!",
  "template_params": {
    "name": "boas_vindas",
    "language": "pt_BR",
    "parameter_format": "POSITIONAL",
    "processed_params": {
      "1": "João",
      "2": "Curso de Tráfego"
    }
  }
}
```

> O `parameter_format` é auto-detectado: primeiro pelo campo `example` do componente BODY (quando o template foi sincronizado com a Meta); senão, inspecionando o texto — só dígitos `{{1}}` → POSITIONAL, nomes `{{customer_name}}` → NAMED. Errar isso causa o erro Meta `#132012 Parameter format does not match`.

---

## 4. Template COM VÍDEO (mídia no header)

Quando o template tem header de mídia, adiciona-se `template_params.header`. O `type` vem de `template.media_kind` (`image` | `video` | `document`) e o `link` de `template.media_url`:

```json
{
  "content": "João, seu acesso ao Curso de Tráfego está liberado! 🎉",
  "template_params": {
    "name": "boas_vindas_video",
    "language": "pt_BR",
    "parameter_format": "NAMED",
    "processed_params": {
      "customer_name": "João",
      "product_name": "Curso de Tráfego"
    },
    "header": {
      "type": "video",
      "link": "https://cdn.exemplo.com/media/welcome.mp4"
    }
  }
}
```

- **Vídeo:** `"type": "video"`, `"link"` aponta para o `.mp4` hospedado.
- **Imagem:** `"type": "image"`, link de `.jpg/.png`.
- **Documento:** `"type": "document"`, link de `.pdf` etc.
- Se o template **não** tem mídia, o objeto `header` simplesmente **não aparece** no payload.

---

## 5. Variáveis — fontes e resolução

Cada variável `{{var}}` do body é resolvida para um valor (string) que entra em `processed_params` e também na renderização do `content`.

### 5.1. Binding configurado no painel (`StepVariableBinding`)

Guardado em `followup_steps.template_variables` como dict `{ nome_da_var: binding }`. O `binding` tem o formato:

```json
{ "source": "<fonte>", "value": "<só quando source = static>" }
```

`source` aceita exatamente um destes 5 valores:

| `source`         | Valor preenchido                                  |
|------------------|---------------------------------------------------|
| `customer_name`  | Nome do cliente (do enrollment)                   |
| `product_name`   | Nome do produto (do enrollment)                   |
| `contact_phone`  | Telefone do contato                               |
| `contact_email`  | E-mail do contato (string vazia se não houver)    |
| `static`         | Texto fixo informado em `value` (obrigatório)     |

Exemplo de `template_variables` no step:

```json
{
  "customer_name": { "source": "customer_name" },
  "product_name":  { "source": "product_name" },
  "cupom":         { "source": "static", "value": "BEMVINDO10" }
}
```

### 5.2. Ordem de resolução (cada variável)

1. **Binding explícito** — se o painel configurou aquela var, usa a fonte indicada.
2. **Convenção por nome** — se não há binding, tenta casar o nome (case-insensitive) com aliases conhecidos:
   - `customer_name` ← `name`, `nome`, `customer`, `cliente`, `first_name`, `firstname`
   - `product_name`  ← `produto`, `product`, `curso`, `course`, `product_name`
   - `contact_email` ← `email`, `e-mail`, `mail`, `contact_email`
   - `contact_phone` ← `phone`, `telefone`, `whatsapp`, `celular`, `contact_phone`
3. **Fallback vazio** — se nada resolver, retorna `""` (string vazia) + log de warning. Isso é proposital: a Meta exige **todas** as variáveis do body preenchidas, senão dá erro `#132000` (número de parâmetros não bate).

> Todas as variáveis presentes no body **mais** as configuradas no step entram em `processed_params` (união). Uma var configurada que não aparece no body ainda é enviada — o ChatNexo decide o uso.

---

## 6. Resumo dos 3 modelos

| Caso              | Campos no payload                                                                 |
|-------------------|-----------------------------------------------------------------------------------|
| Texto normal      | `type: "text"`, `content` (1 POST por fatia do split)                             |
| Template          | `content` (body renderizado) + `template_params{name, language, parameter_format, processed_params}` |
| Template c/ vídeo | igual ao template + `template_params.header{type:"video", link}`                  |

Todos no mesmo endpoint: `POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages`.
