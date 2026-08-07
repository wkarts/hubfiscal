import asyncio
from io import BytesIO
from types import SimpleNamespace

from hubfiscal.services import storage as storage_module


class FakeS3Client:
    def __init__(self) -> None:
        self.put_kwargs: dict = {}
        self.objects: dict[str, bytes] = {}

    def head_bucket(self, **kwargs):
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def create_bucket(self, **kwargs):
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def put_object(self, **kwargs):
        self.put_kwargs = kwargs
        self.objects[str(kwargs["Key"])] = bytes(kwargs["Body"])
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.objects[str(kwargs["Key"])])}

    def delete_object(self, **kwargs):
        self.objects.pop(str(kwargs["Key"]), None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


def settings(sse: str):
    return SimpleNamespace(
        minio_bucket="hubfiscal-test",
        minio_server_side_encryption=sse,
        minio_endpoint="http://127.0.0.1:9000",
        minio_access_key="test",
        minio_secret_key="test-secret",
        minio_region="sa-east-1",
        minio_secure=False,
    )


def make_storage(monkeypatch, sse: str):
    fake = FakeS3Client()
    monkeypatch.setattr(storage_module, "get_settings", lambda: settings(sse))
    monkeypatch.setattr(storage_module.boto3, "client", lambda *args, **kwargs: fake)
    return storage_module.ObjectStorage(), fake


def test_put_does_not_force_sse_without_kms(monkeypatch):
    object_storage, fake = make_storage(monkeypatch, "none")

    async def run():
        await object_storage.put("certificate.enc", b"encrypted")
        assert await object_storage.get("certificate.enc") == b"encrypted"

    asyncio.run(run())
    assert "ServerSideEncryption" not in fake.put_kwargs


def test_put_uses_sse_only_when_explicitly_enabled(monkeypatch):
    object_storage, fake = make_storage(monkeypatch, "AES256")
    asyncio.run(object_storage.put("certificate.enc", b"encrypted"))
    assert fake.put_kwargs["ServerSideEncryption"] == "AES256"
