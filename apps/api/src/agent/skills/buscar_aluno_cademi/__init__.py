from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.buscar_aluno_cademi.skill import BuscarAlunoCademiSkill
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = BuscarAlunoCademi(cademi=adapters.cademi)
    return BuscarAlunoCademiSkill(use_case=use_case)
