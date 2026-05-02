from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.verificar_elegibilidade_reembolso.skill import (
    VerificarElegibilidadeReembolsoSkill,
)
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = VerificarElegibilidadeReembolso(
        hubla=adapters.hubla, legal_history=adapters.legal_history
    )
    return VerificarElegibilidadeReembolsoSkill(use_case=use_case)
