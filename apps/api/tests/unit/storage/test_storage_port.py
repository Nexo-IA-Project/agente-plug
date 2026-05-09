from shared.domain.ports.storage import StorageObject


def test_storage_object_holds_metadata():
    obj = StorageObject(
        url="https://media.example.com/foo.jpg",
        object_key="accounts/abc/templates/foo.jpg",
        size=1024,
        sha256="deadbeef",
        content_type="image/jpeg",
    )
    assert obj.url == "https://media.example.com/foo.jpg"
    assert obj.object_key == "accounts/abc/templates/foo.jpg"
    assert obj.size == 1024
    assert obj.sha256 == "deadbeef"
    assert obj.content_type == "image/jpeg"
