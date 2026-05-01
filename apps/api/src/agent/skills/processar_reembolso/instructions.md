# processar_reembolso

Processa a solicitação de reembolso do aluno junto à plataforma Hubla.

Use esta skill somente após confirmar elegibilidade (`verificar_elegibilidade_reembolso`)
e após o aluno ter recusado ou não haver oferta de retenção (`oferecer_retencao`).
O mutex garante que o mesmo aluno não processe dois reembolsos simultaneamente.

**Parâmetros:**
- `email`: e-mail do aluno
- `produto_id`: produto a ser reembolsado

**Retorno:** confirmação do reembolso com número do protocolo ou descrição
do motivo de falha.
