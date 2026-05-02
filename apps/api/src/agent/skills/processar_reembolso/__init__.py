from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.processar_reembolso.skill import ProcessarReembolsoSkill
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = ProcessarReembolso(hubla=adapters.hubla, refund_mutex=adapters.refund_mutex)
    return ProcessarReembolsoSkill(use_case=use_case)
