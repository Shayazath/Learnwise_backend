
import hashlib
from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from app.config import (
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT_URL,
    R2_REGION,
    validate_r2_config,
)


class R2StorageError(Exception):
    """Raised when an R2 storage operation fails."""


class R2StorageService:

    def __init__(self):
        validate_r2_config()

        self.bucket_name = R2_BUCKET_NAME

        self.client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name=R2_REGION,
            config=Config(
                signature_version="s3v4",
                retries={
                    "max_attempts": 3,
                    "mode": "standard",
                },
                connect_timeout=5,
                read_timeout=30,
            ),
        )

    def upload(
        self,
        file_obj: BinaryIO,
        object_key: str,
        content_type: str,
        checksum_sha256: str,
        content_length: int,
    ) -> str:
        """
        Upload a document to a private R2 bucket.
        Returns the object key, never a public URL.
        """

        if not object_key or object_key.startswith("/"):
            raise ValueError("Invalid storage object key.")

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_obj,
                ContentType=content_type,
                ContentLength=content_length,
                Metadata={
                    "sha256": checksum_sha256,
                },
            )

            return object_key

        except (ClientError, BotoCoreError) as exc:
            raise R2StorageError(
                "Unable to upload document to cloud storage."
            ) from exc

    def download(self, object_key: str):
        """Return a readable R2 object response."""

        try:
            return self.client.get_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )

        except (ClientError, BotoCoreError) as exc:
            error_code = exc.response.get(
                "Error", {}
            ).get("Code")

            if error_code in ("NoSuchKey", "404"):
                return None

            raise R2StorageError(
                "Unable to download document."
            ) from exc

    def exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )
            return True

        except (ClientError, BotoCoreError) as exc:
            error_code = exc.response.get(
                "Error", {}
            ).get("Code")

            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False

            raise R2StorageError(
                "Unable to check document in cloud storage."
            ) from exc

    def delete(self, object_key: str) -> None:
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )

        except (ClientError, BotoCoreError) as exc:
            raise R2StorageError(
                "Unable to delete document from cloud storage."
            ) from exc

    def generate_download_url(
        self,
        object_key: str,
        expires_in: int = 300,
    ) -> str:
        """Generate a short-lived signed download URL."""

        if not 1 <= expires_in <= 3600:
            raise ValueError("Invalid signed URL expiration.")

        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                },
                ExpiresIn=expires_in,
            )

        except (ClientError, BotoCoreError) as exc:
            raise R2StorageError(
                "Unable to generate document download URL."
            ) from exc


@lru_cache(maxsize=1)
def get_storage_service() -> R2StorageService:
    return R2StorageService()


def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
