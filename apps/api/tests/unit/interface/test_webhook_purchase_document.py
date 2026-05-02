from interface.http.schemas.webhook_purchase import PurchaseWebhookPayload


def test_payload_accepts_document_field():
    p = PurchaseWebhookPayload(
        purchase_id="p-001",
        nome="João",
        email="j@e.com",
        telefone="+5511999999999",
        produto="Curso",
        valor=197.0,
        timestamp="2026-04-18T10:00:00Z",
        document="123.456.789-00",
    )
    assert p.document == "123.456.789-00"


def test_payload_document_defaults_to_none():
    p = PurchaseWebhookPayload(
        purchase_id="p-001",
        nome="João",
        email="j@e.com",
        telefone="+5511999999999",
        produto="Curso",
        valor=197.0,
        timestamp="2026-04-18T10:00:00Z",
    )
    assert p.document is None


def test_payload_document_accepts_cnpj():
    p = PurchaseWebhookPayload(
        purchase_id="p-002",
        nome="Empresa",
        email="e@e.com",
        telefone="+5511999999999",
        produto="Curso",
        valor=500.0,
        timestamp="2026-04-18T10:00:00Z",
        document="12.345.678/0001-90",
    )
    assert p.document == "12.345.678/0001-90"
