# apps/api/src/agent/skills/buscar_conhecimento/__init__.py
from agent.skill_loader import Adapters
from agent.skills.buscar_conhecimento.skill import BuscarConhecimentoTool
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


def make_skill(adapters: Adapters) -> BuscarConhecimentoTool:
    use_case = BuscarConhecimento(
        knowledge_repo=adapters.knowledge_repo,
        usage_log_repo=adapters.usage_log_repo,
    )
    return BuscarConhecimentoTool(use_case=use_case)
