# verificar_caso_acesso

Verifica se o aluno já possui um caso de acesso aberto no sistema e qual é
o seu status atual.

Use esta skill após `buscar_aluno_cademi` para determinar se existe um caso
em andamento antes de criar um novo ou enviar um link de acesso. Evita
duplicação de atendimentos.

**Parâmetros:**
- `email`: e-mail do aluno obtido via `buscar_aluno_cademi`

**Retorno:** status do caso atual (aberto, fechado, inexistente) e ID do caso
se existir.
