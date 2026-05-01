# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.verificar_elegibilidade_reembolso.skill import VerificarElegibilidadeReembolsoTool
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


def make_skill(adapters: Adapters) -> VerificarElegibilidadeReembolsoTool:
    use_case = VerificarElegibilidadeReembolso(
        hubla=adapters.hubla, legal_history=adapters.legal_history
    )
    return VerificarElegibilidadeReembolsoTool(use_case=use_case)
