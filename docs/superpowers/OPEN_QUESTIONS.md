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
**Contexto:** Mensagens proativas no WhatsApp exigem template aprovado pela Meta.
**Pergunta:** O template `welcome_purchase` já está criado e aprovado no Meta Business Manager?
- Qual é o nome exato do template?
- Quais são as variáveis (parâmetros `{{1}}`, `{{2}}`, `{{3}}`)?
- Qual é o corpo exato do texto?
- Há botões (call-to-action) no template?

**Impacto:** Bloqueia o envio real da mensagem de boas-vindas em produção.

---

### CQ-W04 — Templates Meta Loja Express
**Contexto:** Follow-ups D+1, D+3, D+7 usam templates Meta aprovados.
**Pergunta:** Os templates `loja_express_d1`, `loja_express_d3`, `loja_express_d7` já estão criados e aprovados?
- Nome exato de cada um no Meta
- Variáveis e corpo do texto de cada um
- Template para D+5 existe? (não listado no PRD)

**Impacto:** Bloqueia os follow-ups da Loja Express em produção.

---

## Capability Access (Spec ③)

### CQ-A02 — Cademi suporta busca por nome + telefone?
**Contexto:** A 3ª tentativa da cascade de busca é por nome+telefone. Não sabemos se a Cademi API tem esse endpoint.
**Pergunta:** A API da Cademi possui endpoint de busca por nome e/ou telefone do aluno?
- Se sim: qual o endpoint e parâmetros?
- Se não: a 3ª tentativa deve escalar diretamente para humano?

**Impacto:** Afeta o nó `search_cademi_cascade` (3ª tentativa). Stub com `NotImplementedError` até confirmação.

---

## Capability Refund & Retention (Spec ④)

### CQ-R03 — O que é "aluno CMP" e qual é a argumentação especial?
**Contexto:** O PRD menciona "aluno CMP insistente" com argumentação especial sem N1/N2 padrão.
**Pergunta:**
- O que significa CMP neste contexto?
- Qual é a argumentação especial aplicada?
- Como identificar um aluno CMP (tag, histórico, campo na Hubla)?

**Impacto:** Afeta o nó `retention_loop`. Stub por ora sem tratamento especial.

---

## Capability Loja Express (Spec ⑤)

### CQ-L01 — O que é o "formulário" da Loja Express?
**Contexto:** O PRD menciona "enviar passo a passo do formulário" no D+0 e "verificar se formulário foi respondido" no D+1.
**Pergunta:**
- O que é esse formulário? (Google Forms, Typeform, sistema próprio?)
- Como o backend sabe se o formulário foi respondido? (webhook, polling, preenchimento manual?)
- Qual é o link/URL do formulário?

**Impacto:** Afeta os nós D+0 e D+1 do subgraph. Stub por ora.

---

### CQ-L02 — Integração de status da loja (D+3, D+5, D+7)
**Contexto:** PRD diz "verificar status da loja, informar progresso" (D+3) e "verificar bloqueio, acionar operação" (D+5). A integração é "A definir por tenant".
**Pergunta:**
- Para G2 Educação: como verificamos o status da loja? (planilha Google Sheets, sistema do fornecedor, manual?)
- Quem é o "fornecedor" da loja?
- O que significa "acionar operação" no D+5? (notificar alguém via Slack/email/WhatsApp?)

**Impacto:** Afeta os nós D+3, D+5 e D+7. Stubs por ora.

---

### CQ-L03 — Template Meta D+5 da Loja Express
**Contexto:** O PRD lista templates para D+1, D+3 e D+7, mas não menciona template para D+5.
**Pergunta:** O D+5 usa template Meta aprovado ou pode ser texto livre (se dentro da janela 24h)?

**Impacto:** Afeta o nó D+5.

---

## Capability Knowledge (Spec ⑦)

### CQ-K01 — Lista consolidada de sinônimos (160+ termos)
**Contexto:** A Knowledge Capability expande a query do aluno com sinônimos mapeados (PRD 7.4). O PRD menciona "160+ termos mapeados" mas não fornece a lista.
**Pergunta:**
- Existe uma lista pronta dos 160+ termos e sinônimos da Sofia atual (G2 Educação)?
- Se sim: como importar/transcrever?
- Se não: precisamos consolidar com a equipe antes da implementação da Fase 1?

**Impacto:** Sem a lista, a Tentativa 2 da Knowledge Capability vira a mesma coisa que a Tentativa 1. Stub inicial com 10-20 termos comuns até a lista real.

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

### CQ-W05 — Comportamento quando email de compra ≠ email Cademi
**Resposta (PRD 7.2):** Oferecer atualizar cadastro antes de reenviar. O agente deve informar que o email de compra difere do cadastro e perguntar se o aluno quer atualizar.
**Spec atualizado:** ③ Access — nó `search_cademi_cascade`.

---

### CQ-A01 — Formato do que enviar ao aluno após encontrar na Cademi
**Resposta (PRD 7.2):** Link nominal de auto-login. "Regra: link de acesso deve ser nominal (auto-login) — aluno não cria senha." Dentro da janela 24h → texto livre com o link. Fora da janela → template Meta aprovado.
**Spec atualizado:** ③ Access — nó `send_access`.

---

### CQ-R01 — Mecanismo para processar reembolso na Hubla
**Resposta (PRD 12):** Playwright (browser automation). "A Hubla não tem API REST pública. Toda operação é via browser automation (Playwright). Timeout 150s, concorrência=1, self-healing de sessão, MFA via IMAP Gmail."
**Spec atualizado:** ④ Refund — `HublaClient.process_refund()`.

---

### CQ-R02 — Ofertas de retenção N1 e N2 por produto
**Resposta (PRD 7.3):** Ofertas fixas para G2 Educação:
- N1 (Acesso Vitalício): transforma acesso em permanente. Gratuito para o aluno.
- N2 (Mentoria de Tráfego): curso de tráfego pago liberado gratuitamente. Gratuito para o aluno.
**Spec atualizado:** ④ Refund — nó `retention_loop`.

---

### CQ-R04 — API Hubla para busca de compra por email
**Resposta (PRD 12):** A Hubla não tem API REST pública. Busca de compra também via Playwright. Timeout 150s, concorrência=1.
**Spec atualizado:** ④ Refund — `HublaClient.get_purchase_by_email()`.
