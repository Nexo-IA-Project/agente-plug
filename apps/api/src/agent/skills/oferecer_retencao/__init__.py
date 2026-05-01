# apps/api/src/agent/skills/oferecer_retencao/__init__.py
from agent.skill_loader import Adapters
from agent.skills.oferecer_retencao.skill import OfereceRetencaoTool
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


def make_skill(adapters: Adapters) -> OfereceRetencaoTool:
    use_case = OfereceRetencao(hubla=adapters.hubla, refund_repo=adapters.refund_repo)
    return OfereceRetencaoTool(use_case=use_case)
