# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/__init__.py
from agent.skill_loader import Adapters
from agent.skills.buscar_conhecimento_com_contexto.skill import BuscarConhecimentoComContextoTool
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


def make_skill(adapters: Adapters) -> BuscarConhecimentoComContextoTool:
    use_case = BuscarConhecimentoComContexto(
        knowledge_repo=adapters.knowledge_repo,
        usage_log_repo=adapters.usage_log_repo,
    )
    return BuscarConhecimentoComContextoTool(use_case=use_case)
