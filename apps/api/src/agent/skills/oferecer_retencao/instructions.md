# oferecer_retencao

Oferece uma alternativa ao reembolso para tentar reter o aluno — por exemplo,
uma pausa na assinatura, acesso a suporte prioritário, ou desconto em renovação.

Use esta skill após confirmar elegibilidade (`verificar_elegibilidade_reembolso`)
mas ANTES de processar o reembolso. A oferta de retenção deve ser apresentada
como uma opção, nunca como imposição. Se o aluno recusar, prossiga com
`processar_reembolso`.

**Parâmetros:**
- `email`: e-mail do aluno
- `produto_id`: produto para o qual o reembolso está sendo solicitado

**Retorno:** oferta de retenção gerada ou indicação de que não há oferta
disponível para este perfil.
