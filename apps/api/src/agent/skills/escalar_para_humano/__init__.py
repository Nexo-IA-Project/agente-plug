from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.escalar_para_humano.skill import EscalarParaHumanoSkill


def make_skill(adapters: Adapters) -> BaseSkill:
    return EscalarParaHumanoSkill(chatnexo=adapters.chatnexo)
