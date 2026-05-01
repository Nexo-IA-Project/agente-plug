# apps/api/src/agent/skills/verificar_caso_acesso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.verificar_caso_acesso.skill import VerificarCasoAcessoTool
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


def make_skill(adapters: Adapters) -> VerificarCasoAcessoTool:
    use_case = VerificarCasoAcesso(access_repo=adapters.access_repo)
    return VerificarCasoAcessoTool(use_case=use_case)
