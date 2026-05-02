from agent.skill import BaseSkill
from agent.skill_loader import Adapters
from agent.skills.verificar_caso_acesso.skill import VerificarCasoAcessoSkill
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


def make_skill(adapters: Adapters) -> BaseSkill:
    use_case = VerificarCasoAcesso(access_repo=adapters.access_repo)
    return VerificarCasoAcessoSkill(use_case=use_case)
