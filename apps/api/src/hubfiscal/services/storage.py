from __future__ import annotations

import asyncio

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..core.config import get_settings


class ObjectStorageError(RuntimeError):
    """Falha operacional no backend S3/MinIO."""


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.server_side_encryption = (
            None
            if settings.minio_server_side_encryption == "none"
            else settings.minio_server_side_encryption
        )
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name=settings.minio_region,
            config=Config(signature_version="s3v4"),
            use_ssl=settings.minio_secure,
        )

    async def ensure_bucket(self) -> None:
        def work() -> None:
            try:
                self.client.head_bucket(Bucket=self.bucket)
                return
            except ClientError as exc:
                error = exc.response.get("Error", {})
                code = str(error.get("Code", ""))
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status != 404 and code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise
            self.client.create_bucket(Bucket=self.bucket)

        try:
            await asyncio.to_thread(work)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ObjectStorageError(
                f"Não foi possível acessar o bucket S3/MinIO '{self.bucket}'"
            ) from exc

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        await self.ensure_bucket()
        kwargs: dict[str, object] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if self.server_side_encryption:
            kwargs["ServerSideEncryption"] = self.server_side_encryption
        try:
            await asyncio.to_thread(self.client.put_object, **kwargs)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ObjectStorageError(
                f"Não foi possível gravar '{key}' no S3/MinIO"
            ) from exc

    async def get(self, key: str) -> bytes:
        def work() -> bytes:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()

        try:
            return await asyncio.to_thread(work)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ObjectStorageError(
                f"Não foi possível ler '{key}' do S3/MinIO"
            ) from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=self.bucket,
                Key=key,
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ObjectStorageError(
                f"Não foi possível remover '{key}' do S3/MinIO"
            ) from exc


storage = ObjectStorage()
