# apps/api/src/agent/skills/processar_reembolso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.processar_reembolso.skill import ProcessarReembolsoTool
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


def make_skill(adapters: Adapters) -> ProcessarReembolsoTool:
    use_case = ProcessarReembolso(hubla=adapters.hubla, refund_mutex=adapters.refund_mutex)
    return ProcessarReembolsoTool(use_case=use_case)
