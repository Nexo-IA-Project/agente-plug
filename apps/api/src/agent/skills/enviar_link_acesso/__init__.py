# apps/api/src/agent/skills/enviar_link_acesso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.enviar_link_acesso.skill import EnviarLinkAcessoTool
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


def make_skill(adapters: Adapters) -> EnviarLinkAcessoTool:
    use_case = EnviarLinkAcesso(cademi=adapters.cademi, chatnexo=adapters.chatnexo)
    return EnviarLinkAcessoTool(use_case=use_case)
