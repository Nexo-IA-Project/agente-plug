from shared.adapters.meta.templates import InMemoryMetaTemplates


async def test_registered_template_can_be_retrieved() -> None:
    registry = InMemoryMetaTemplates()
    registry.register(
        name="welcome_purchase",
        meta_id="MT-001",
        language="pt_BR",
        variables=["name", "product", "link"],
    )
    found = await registry.get_approved_template(name="welcome_purchase")
    assert found is not None
    assert found["meta_id"] == "MT-001"
    assert found["variables"] == ["name", "product", "link"]


async def test_unknown_template_returns_none() -> None:
    registry = InMemoryMetaTemplates()
    assert await registry.get_approved_template(name="nope") is None
