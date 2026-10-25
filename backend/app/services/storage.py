from datetime import UTC, datetime
from typing import Any

import boto3
import structlog
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.errors import AppException, ErrorCode

logger = structlog.get_logger("service.storage")


class StorageService:
    def __init__(self) -> None:
        self.endpoint_url = settings.S3_ENDPOINT
        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
            region_name="us-east-1",
        )

    def generate_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str | None = None,
        max_size_bytes: int | None = None,
        expires_in: int = 3600,
    ) -> dict[str, Any]:
        """Generate a presigned PUT URL for client-side direct upload."""
        if max_size_bytes is None:
            max_size_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": s3_key,
        }
        if content_type:
            params["ContentType"] = content_type

        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return {
                "upload_url": url,
                "s3_key": s3_key,
                "expires_in": expires_in,
                "max_size_bytes": max_size_bytes,
            }
        except ClientError as e:
            logger.error("failed_generating_presigned_upload_url", error=str(e), s3_key=s3_key)
            raise AppException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Failed to generate upload URL",
                status_code=500,
            ) from e

    def generate_presigned_download_url(
        self,
        s3_key: str,
        filename: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned GET URL for secure downloading."""
        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": s3_key,
        }
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        try:
            url: str = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error("failed_generating_presigned_download_url", error=str(e), s3_key=s3_key)
            raise AppException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Failed to generate download URL",
                status_code=500,
            ) from e

    def object_exists(self, s3_key: str) -> bool:
        """Check whether an object exists in the S3 bucket."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False

    def get_object_metadata(self, s3_key: str) -> dict[str, Any]:
        """Get object head metadata (size, content type, etag)."""
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return {
                "content_length": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", "application/octet-stream"),
                "etag": response.get("ETag", "").strip('"'),
                "last_modified": response.get("LastModified", datetime.now(UTC)),
            }
        except ClientError as e:
            logger.error("object_not_found", s3_key=s3_key, error=str(e))
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Object not found in storage: {s3_key}",
                status_code=404,
            ) from e

    def get_object_bytes(self, s3_key: str) -> bytes:
        """Fetch raw bytes of an object."""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=s3_key)
            body: bytes = response["Body"].read()
            return body
        except ClientError as e:
            logger.error("failed_fetching_object_bytes", s3_key=s3_key, error=str(e))
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"File not found in storage: {s3_key}",
                status_code=404,
            ) from e

    def put_object_bytes(
        self, s3_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Store bytes directly into S3."""
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=data,
                ContentType=content_type,
            )
        except ClientError as e:
            logger.error("failed_putting_object_bytes", s3_key=s3_key, error=str(e))
            raise AppException(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to store file in storage: {s3_key}",
                status_code=500,
            ) from e

    def delete_object(self, s3_key: str) -> None:
        """Delete an object from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
        except ClientError as e:
            logger.error("failed_deleting_object", s3_key=s3_key, error=str(e))
