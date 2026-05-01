# apps/api/src/agent/skills/escalar_para_humano/__init__.py
from agent.skill_loader import Adapters
from agent.skills.escalar_para_humano.skill import EscalarParaHumanoTool


def make_skill(adapters: Adapters) -> EscalarParaHumanoTool:
    return EscalarParaHumanoTool(chatnexo=adapters.chatnexo)
