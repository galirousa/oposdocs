"""Presigned URL helpers on top of the default S3 storage."""

from django.conf import settings
from django.core.files.storage import default_storage


def _public_client() -> object:
    """Client bound to the browser-facing endpoint. SigV4 signs the Host
    header, so URLs must be generated against the hostname the browser will
    actually hit (in local dev: localhost:9000, not the internal minio:9000)."""
    public_endpoint = getattr(settings, "AWS_S3_PUBLIC_ENDPOINT_URL", "")
    client = default_storage.connection.meta.client
    if not public_endpoint or public_endpoint == default_storage.endpoint_url:
        return client
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=public_endpoint,
        aws_access_key_id=default_storage.access_key,
        aws_secret_access_key=default_storage.secret_key,
        region_name=default_storage.region_name,
    )


def presigned_get_url(storage_key: str, expire: int | None = None) -> str:
    """Short-lived presigned GET, generated per request AFTER the permission
    check. Callers must send Cache-Control: private, no-store with the
    redirect — a private document must never land in an edge cache."""
    return _public_client().generate_presigned_url(  # type: ignore[attr-defined]
        "get_object",
        Params={"Bucket": default_storage.bucket_name, "Key": storage_key},
        ExpiresIn=expire or settings.PRESIGNED_URL_EXPIRY,
    )


def presigned_put_url(storage_key: str, expire: int = 600) -> str:
    """Presigned PUT for direct-to-storage uploads from the browser."""
    client = default_storage.connection.meta.client
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": default_storage.bucket_name,
            "Key": storage_key,
        },
        ExpiresIn=expire,
    )
