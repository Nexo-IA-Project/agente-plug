# enviar_link_acesso

Envia um link de acesso ao curso para o aluno via ChatNexo (WhatsApp).

Use esta skill como etapa final do fluxo de acesso, após confirmar que o aluno
existe (`buscar_aluno_cademi`) e verificar o status do caso (`verificar_caso_acesso`).
Só envie o link se o caso estiver aberto ou inexistente — nunca reenvie se o
status já for "resolvido".

**Parâmetros:**
- `email`: e-mail do aluno
- `phone`: telefone do aluno para entrega da mensagem

**Retorno:** confirmação de envio ou descrição do erro.
