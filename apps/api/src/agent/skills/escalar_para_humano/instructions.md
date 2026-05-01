# escalar_para_humano

Escala o atendimento para um agente humano via ChatNexo.

Use esta skill quando:
- O aluno solicitar falar com um humano explicitamente
- Nenhuma outra skill conseguir resolver o problema após tentativas
- Um guard disparar (menção legal, loop detectado)
- `buscar_conhecimento_com_contexto` retornar sinal de escalação

Após chamar esta skill, o atendimento sai do controle do agente de IA.
Não tente continuar o atendimento após a escalação.

**Parâmetros:** nenhum

**Retorno:** confirmação de que o atendimento foi escalado.
