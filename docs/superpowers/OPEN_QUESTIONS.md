# NexoIA — Questões em Aberto (Regras de Negócio)

> ⚠️  IMPORTANTE: Antes de implementar qualquer item marcado com `TODO` nos specs,
> o agente/desenvolvedor DEVE perguntar ao responsável do produto sobre cada questão abaixo.
> Não assuma nem invente valores padrão para regras de negócio críticas.

---

## Capability Welcome (Spec ②)

### CQ-W01 — Documentação da API Cademi
**Contexto:** A Capability Welcome precisa buscar dados do aluno e gerar link nominal de auto-login na plataforma Cademi.
**Pergunta:** Qual é a documentação da API Cademi?
- URL base da API
- Mecanismo de autenticação (API Key? OAuth? Bearer token?)
- Endpoint para busca de aluno por email
- Endpoint para busca de aluno por CPF
- Endpoint para geração de link nominal de auto-login
- Existe rate limit?

**Impacto:** Bloqueia implementação de `CademiClient`. Stub com `NotImplementedError` no lugar até ser respondido.

---

### CQ-W02 — Prazo de expiração do link de auto-login Cademi
**Contexto:** O template `welcome_purchase` inclui o link nominal de auto-login. O mesmo link é reutilizado no reminder D+1?
**Pergunta:** O link de acesso gerado pela Cademi expira? Se sim, em quanto tempo?
- **Se expira:** precisamos gerar um novo link no momento do D+1 (nova chamada à Cademi API)
- **Se não expira:** o mesmo link pode ser reutilizado no D+1

**Impacto:** Afeta o nó `schedule_d1` — se o link expira, o job D+1 precisa chamar a Cademi novamente ao executar.

---

### CQ-W03 — Template Meta `welcome_purchase`
**Contexto:** Mensagens proativas no WhatsApp exigem template aprovado pela Meta. O template precisa estar cadastrado no Meta Business Manager antes de ser usado.
**Pergunta:** O template `welcome_purchase` já está criado e aprovado no Meta Business Manager?
- Qual é o nome exato do template?
- Quais são as variáveis (parâmetros `{{1}}`, `{{2}}`, `{{3}}`)?
- Qual é o corpo exato do texto?
- Há botões (call-to-action) no template?

**Impacto:** Bloqueia o envio real da mensagem de boas-vindas em produção.

---

### CQ-W04 — Template Meta `access_reminder_d1`
**Contexto:** Lembrete enviado no D+1 se o aluno não confirmou acesso.
**Pergunta:** O template `access_reminder_d1` já está criado e aprovado?
- Nome exato no Meta
- Variáveis e corpo do texto

**Impacto:** Bloqueia o envio do reminder D+1 em produção.

---

### CQ-W05 — Comportamento quando email de compra ≠ email Cademi
**Contexto:** O spec define que se o email da compra (Hubla) não for encontrado na Cademi, o agente escalona para humano.
**Pergunta:** Qual deve ser o comportamento exato?
- O agente deve informar o aluno sobre o problema de cadastro?
- O agente deve pedir o CPF para tentar outra busca?
- Após quantas tentativas escala definitivamente?

**Impacto:** Afeta o fluxo de fallback do nó `fetch_cademi`.

---

## Capability Access (Spec ③)

### CQ-A01 — Formato do que enviar ao aluno após encontrar na Cademi
**Contexto:** A Capability Access encontra o aluno na Cademi e precisa enviar as informações de acesso. Não está definido ainda se enviamos link nominal de auto-login ou outra forma de acesso.
**Pergunta:** O que exatamente enviamos ao aluno quando encontramos o cadastro?
- Link nominal de auto-login (igual ao Welcome)?
- Email + senha provisória?
- Outro formato?
- A mensagem pode ser texto livre (dentro da janela 24h) ou precisa de template Meta aprovado?

**Impacto:** Bloqueia o nó `send_access`. Stub com `NotImplementedError` enquanto não confirmado.

---

### CQ-A02 — Cademi suporta busca por nome + telefone?
**Contexto:** A 3ª tentativa da cascade de busca é por nome+telefone. Não sabemos se a Cademi API tem esse endpoint.
**Pergunta:** A API da Cademi possui endpoint de busca por nome e/ou telefone do aluno?
- Se sim: qual o endpoint e parâmetros?
- Se não: a 3ª tentativa deve escalar diretamente para humano?

**Impacto:** Afeta o nó `search_cademi_cascade` (3ª tentativa). Stub com `NotImplementedError` até confirmação.

---

## Capability Refund & Retention (Spec ④)

### CQ-R01 — Mecanismo para processar reembolso na Hubla
**Contexto:** A Capability Refund precisa processar o reembolso programaticamente. A Hubla não tem API pública documentada para isso — o único mecanismo encontrado é o painel web.
**Pergunta:** Como processar o reembolso automaticamente?
- A Hubla tem API privada para processar reembolsos (endpoint + autenticação)?
- Ou usamos Playwright para automatizar o painel web `app.hub.la/refund`?
- Ou o processamento é feito manualmente por um operador humano (handoff)?

**Impacto:** Bloqueia implementação de `HublaClient.process_refund()`. Stub com `NotImplementedError` até ser respondido.

---

### CQ-R02 — Ofertas de retenção N1 e N2 por produto
**Contexto:** O fluxo de retenção oferece N1 (Acesso Vitalício) e N2 (Mentoria de Tráfego) antes de processar o reembolso.
**Pergunta:** Essas ofertas são fixas para todos os produtos, ou variam por produto?
- Se variam: qual é o mapeamento produto → N1/N2?
- As ofertas têm algum custo ou são sempre gratuitas para o aluno?

**Impacto:** Afeta o nó `retention_loop`. Stub por ora com ofertas fixas.

---

### CQ-R03 — O que é "aluno CMP" e qual é a argumentação especial?
**Contexto:** O PRD menciona "aluno CMP insistente" com argumentação especial sem N1/N2 padrão.
**Pergunta:**
- O que significa CMP neste contexto?
- Qual é a argumentação especial aplicada?
- Como identificar um aluno CMP (tag, histórico, campo na Hubla)?

**Impacto:** Afeta o nó `retention_loop`. Stub por ora sem tratamento especial.

---

### CQ-R04 — API Hubla para busca de compra por email
**Contexto:** O nó `check_deadline` precisa buscar a compra do aluno na Hubla para verificar o prazo CDC.
**Pergunta:** A Hubla tem endpoint REST para buscar compras/faturas por email do comprador?
- Se sim: URL, autenticação e campos retornados?
- Se não: como verificamos o prazo? (dados do webhook já salvos no AccessCase?)

**Impacto:** Bloqueia `HublaClient.get_purchase_by_email()`. Stub com `NotImplementedError` até confirmação.

---

## Geral / Infraestrutura

### CQ-G01 — Credenciais Cademi por ambiente
**Pergunta:** As credenciais da Cademi API são as mesmas para dev/staging/prod, ou cada ambiente tem suas próprias?
**Impacto:** Afeta o `.env.example` e a estratégia de secrets.

---

## Como usar este arquivo

1. Quando o agente encontrar um `TODO` que referencia `OPEN_QUESTIONS.md`, ele deve **parar e perguntar** ao usuário antes de continuar.
2. Quando uma questão for respondida: mover para a seção **Respondidas** abaixo e atualizar o spec correspondente.
3. Manter este arquivo atualizado a cada novo spec brainstormado.

---

## Respondidas

*(nenhuma ainda)*
