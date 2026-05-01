# buscar_conhecimento_com_contexto

Busca informações na base de conhecimento enriquecendo a query com dados
contextuais do aluno (nome, cursos ativos) para melhorar a relevância.

Use esta skill como fallback após `buscar_conhecimento` não encontrar
resultados com a query original. O contexto adicional permite que a busca
vetorial encontre trechos mais específicos para o perfil do aluno.

**Parâmetros:**
- `query`: pergunta ou tópico original
- `contexto_aluno`: dados do aluno para enriquecer a busca (nome, cursos, etc.)

**Retorno:** trechos relevantes da base de conhecimento ou mensagem indicando
que nenhuma informação foi localizada mesmo com contexto adicional. Se ainda
não encontrar, a skill sinaliza para escalar para humano.
