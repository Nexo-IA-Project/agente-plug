# apps/api/src/agent/skills/buscar_aluno_cademi/__init__.py
from agent.skill_loader import Adapters
from agent.skills.buscar_aluno_cademi.skill import BuscarAlunoCademiTool
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


def make_skill(adapters: Adapters) -> BuscarAlunoCademiTool:
    use_case = BuscarAlunoCademi(cademi=adapters.cademi)
    return BuscarAlunoCademiTool(use_case=use_case)
