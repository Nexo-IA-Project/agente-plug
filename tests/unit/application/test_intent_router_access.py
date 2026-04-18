from nexoia.application.intent_router import route_to_capability


def test_intent_access_routes_to_access_subgraph():
    node_name = route_to_capability(intent="access")
    assert node_name == "capability_access"


def test_intent_refund_routes_to_refund():
    node_name = route_to_capability(intent="refund")
    assert node_name == "capability_refund"


def test_unknown_intent_falls_back_to_knowledge_or_default():
    node_name = route_to_capability(intent="chit_chat")
    assert node_name == "capability_knowledge"


def test_welcome_response_routes_to_welcome():
    assert route_to_capability(intent="welcome_response") == "capability_welcome"
