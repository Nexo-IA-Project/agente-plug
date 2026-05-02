from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.oferecer_retencao.skill import OfereceRetencaoSkill
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = OfereceRetencao(hubla=adapters.hubla, refund_repo=adapters.refund_repo)
    return OfereceRetencaoSkill(use_case=use_case)
