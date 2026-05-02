from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.enviar_link_acesso.skill import EnviarLinkAcessoSkill
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = EnviarLinkAcesso(cademi=adapters.cademi, chatnexo=adapters.chatnexo)
    return EnviarLinkAcessoSkill(use_case=use_case)
