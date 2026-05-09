from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import boto3
import structlog
from botocore.exceptions import ClientError

from shared.domain.ports.storage import StorageObject, StoragePort

log = structlog.get_logger(__name__)


class R2Storage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_base_url: str,
    ) -> None:
        self._bucket = bucket_name
        self._public_base_url = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    @classmethod
    def from_settings(cls, settings: Any) -> R2Storage:
        if not all([
            settings.r2_account_id,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
            settings.r2_public_base_url,
        ]):
            raise RuntimeError("R2 não configurado: defina R2_* em .env.local")
        return cls(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket_name,
            public_base_url=settings.r2_public_base_url,
        )

    @classmethod
    def from_settings_or_null(cls, settings: Any) -> StoragePort:
        """Retorna R2Storage se configurado, senão NullStorage (no-op).

        Permite que use cases que NÃO dependem efetivamente de storage
        (ex.: deletar template sem mídia) sigam recebendo um StoragePort
        sempre presente, sem `Optional` espalhando guards.
        """
        # Import local pra evitar dependência circular módulo↔módulo.
        from shared.adapters.storage.null_storage import NullStorage

        try:
            return cls.from_settings(settings)
        except RuntimeError:
            return NullStorage()

    async def upload(
        self, *, key: str, data: bytes, content_type: str
    ) -> StorageObject:
        sha256 = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": sha256},
        )
        log.info("r2_upload", key=key, size=len(data), sha256=sha256)
        return StorageObject(
            url=f"{self._public_base_url}/{key}",
            object_key=key,
            size=len(data),
            sha256=sha256,
            content_type=content_type,
        )

    async def delete(self, *, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )
        log.info("r2_delete", key=key)

    async def head(self, *, key: str) -> StorageObject | None:
        try:
            resp = await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return None
            raise
        return StorageObject(
            url=f"{self._public_base_url}/{key}",
            object_key=key,
            size=int(resp.get("ContentLength", 0)),
            sha256=resp.get("Metadata", {}).get("sha256", ""),
            content_type=resp.get("ContentType", ""),
        )

    async def download(self, *, key: str) -> bytes:
        """Baixa bytes do objeto via S3 API (não via URL pública)."""
        resp = await asyncio.to_thread(
            self._client.get_object, Bucket=self._bucket, Key=key
        )
        body = resp["Body"]
        # boto3 stream → bytes
        data = await asyncio.to_thread(body.read)
        log.info("r2_download", key=key, size=len(data))
        return data
