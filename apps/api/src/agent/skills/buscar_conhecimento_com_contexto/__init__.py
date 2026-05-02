from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.buscar_conhecimento_com_contexto.skill import BuscarConhecimentoComContextoSkill
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = BuscarConhecimentoComContexto(
        knowledge_repo=adapters.knowledge_repo,
        usage_log_repo=adapters.usage_log_repo,
    )
    return BuscarConhecimentoComContextoSkill(use_case=use_case)
