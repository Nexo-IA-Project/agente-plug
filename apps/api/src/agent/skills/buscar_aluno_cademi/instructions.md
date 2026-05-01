# buscar_aluno_cademi

Busca os dados de um aluno na plataforma Cademi a partir do número de telefone.

Use esta skill quando precisar identificar o aluno antes de realizar qualquer
operação de acesso (verificar caso, enviar link). A skill retorna o nome, e-mail
e status de matrícula do aluno.

**Parâmetros:**
- `phone`: número de telefone do aluno no formato internacional (ex: 5511999998888)

**Retorno:** dados do aluno (nome, email, cursos ativos) ou mensagem de erro
se o aluno não for encontrado.
