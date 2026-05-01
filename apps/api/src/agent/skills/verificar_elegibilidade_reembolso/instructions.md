# verificar_elegibilidade_reembolso

Verifica se o aluno é elegível para solicitar reembolso com base nas políticas
de reembolso vigentes e no histórico de compras.

Use esta skill como primeiro passo do fluxo de reembolso, antes de oferecer
retenção ou processar o reembolso. A elegibilidade considera: prazo desde a
compra, tipo de produto, e se já houve reembolso anterior.

**Parâmetros:**
- `email`: e-mail do aluno
- `produto_id`: identificador do produto para o qual o reembolso é solicitado

**Retorno:** elegível (booleano), motivo em caso de inelegibilidade, e prazo
restante para reembolso se elegível.
