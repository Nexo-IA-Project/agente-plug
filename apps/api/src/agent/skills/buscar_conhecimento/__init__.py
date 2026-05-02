from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.buscar_conhecimento.skill import BuscarConhecimentoSkill
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = BuscarConhecimento(
        knowledge_repo=adapters.knowledge_repo,
        usage_log_repo=adapters.usage_log_repo,
    )
    return BuscarConhecimentoSkill(use_case=use_case)
