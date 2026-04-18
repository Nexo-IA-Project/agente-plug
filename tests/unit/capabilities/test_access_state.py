from nexoia.application.capabilities.access import AccessState, build_access_subgraph


def test_access_state_fields():
    state: AccessState = {
        "account_id": 1,
        "correlation_id": "corr-1",
        "messages": [],
        "access_case_id": None,
        "student_email": None,
        "student_cpf": None,
        "student_name": None,
        "student_phone": "+5511999999999",
        "cademi_student": None,
        "search_attempts": 0,
        "cpf_asked": False,
        "access_link": None,
        "out_of_scope": False,
        "email_mismatch_pending": False,
    }
    assert state["student_phone"] == "+5511999999999"
    assert state["search_attempts"] == 0
    assert state["cpf_asked"] is False


def test_build_access_subgraph_is_compilable():
    graph = build_access_subgraph()
    compiled = graph.compile()
    assert compiled is not None
