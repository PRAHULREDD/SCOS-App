"""
SCOS Storage Abstraction Layer (Phase 6.1)

Provides a unified asynchronous interface for file persistence supporting:
1. LocalStorageService: Local filesystem adapter for development and isolated testing.
2. S3StorageService: S3-compatible adapter for Cloudflare R2 / AWS S3 production.
3. Factory get_storage_service(): Environment-based provider selection with strict validation.
"""
from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
from typing import Any, NamedTuple, Optional
import uuid

import boto3
import botocore
import botocore.config
import botocore.exceptions


class StoredFile(NamedTuple):
    """Encapsulates retrieved object content and preserved MIME type."""
    content: bytes
    content_type: str

    def to_stream(self) -> io.BytesIO:
        """Returns in-memory binary stream suitable for StreamingResponse."""
        return io.BytesIO(self.content)


class StorageError(Exception):
    """Base exception for all storage service errors."""
    pass


class StorageFileNotFoundError(StorageError, FileNotFoundError):
    """Raised when the requested storage key does not exist."""
    pass


class StorageConfigurationError(StorageError):
    """Raised when storage configuration is invalid or missing required parameters."""
    pass


class StoragePathTraversalError(StorageError, ValueError):
    """Raised when a storage key attempts illegal path traversal."""
    pass


def validate_storage_key(key: str, storage_root: Optional[Path] = None) -> str:
    """
    Validates that a storage key is well-formed, non-empty, and does not escape
    the root directory or contain illegal path characters.
    """
    if not key or not isinstance(key, str):
        raise StoragePathTraversalError("Storage key must be a non-empty string.")

    # Normalize backslashes to forward slashes and strip whitespace
    clean_key = key.replace("\\", "/").strip()
    if not clean_key:
        raise StoragePathTraversalError("Storage key cannot be empty or whitespace.")

    if "\0" in clean_key:
        raise StoragePathTraversalError("Storage key contains invalid null characters.")

    parts = clean_key.split("/")
    for part in parts:
        if part in ("..", "."):
            raise StoragePathTraversalError(
                f"Storage key contains illegal path traversal segment '{part}': '{key}'"
            )

    if clean_key.startswith("/"):
        raise StoragePathTraversalError(f"Storage key cannot be an absolute path: '{key}'")

    if storage_root is not None:
        root_resolved = storage_root.resolve()
        target_resolved = (storage_root / clean_key).resolve()
        try:
            target_resolved.relative_to(root_resolved)
        except ValueError:
            raise StoragePathTraversalError(f"Storage key escapes storage root: '{key}'")

    return clean_key


class BaseStorageService(ABC):
    """Abstract asynchronous base class for storage adapters."""

    @abstractmethod
    async def save_file(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None
    ) -> str:
        """
        Persists file content under the specified key and preserves content_type.
        Returns the normalized key.
        """
        pass

    @abstractmethod
    async def get_file(self, key: str) -> StoredFile:
        """
        Retrieves file content and preserved content_type for the specified key.
        Raises StorageFileNotFoundError if key does not exist.
        """
        pass

    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """
        Idempotently deletes the file associated with the specified key.
        Guarantees that the key does not exist in storage upon return.
        Returns True if the operation completed successfully (including if the object was already absent).
        Raises StorageError if deletion could not be completed.
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Checks whether an object exists under the specified key.
        Returns True if present, False otherwise.
        """
        pass


class LocalStorageService(BaseStorageService):
    """
    Local filesystem storage adapter.
    Uses atomic writes, key sandboxing against path traversal, and asynchronous
    offloading via asyncio.to_thread to avoid blocking the FastAPI event loop.
    """

    def __init__(self, storage_root: Optional[Path] = None):
        if storage_root is not None:
            self.storage_root = Path(storage_root).resolve()
        else:
            self.storage_root = (
                Path(__file__).resolve().parent.parent.parent / "uploads" / "proof_photos"
            ).resolve()

    def _detect_content_type(self, file_path: Path, meta_path: Path) -> str:
        if meta_path.is_file():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    if isinstance(meta, dict) and "content_type" in meta:
                        return str(meta["content_type"])
            except Exception:
                pass

        ext = file_path.suffix.lower()
        ext_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".json": "application/json",
            ".txt": "text/plain",
        }
        if ext in ext_map:
            return ext_map[ext]

        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
                if header.startswith(b"\xff\xd8\xff"):
                    return "image/jpeg"
                if header.startswith(b"\x89PNG\r\n\x1a\n"):
                    return "image/png"
                if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
                    return "image/webp"
        except Exception:
            pass

        return "application/octet-stream"

    def _sync_save(self, key: str, content: bytes, content_type: Optional[str]) -> str:
        clean_key = validate_storage_key(key, self.storage_root)
        target_path = self.storage_root / clean_key
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        temp_path = target_dir / f".tmp_{target_path.name}_{uuid.uuid4().hex[:8]}"
        try:
            with open(temp_path, "wb") as f:
                f.write(content)
            os.replace(temp_path, target_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

        if content_type:
            meta_path = target_dir / f"{target_path.name}.meta.json"
            temp_meta = target_dir / f".tmp_{target_path.name}.meta_{uuid.uuid4().hex[:8]}"
            try:
                with open(temp_meta, "w", encoding="utf-8") as f:
                    json.dump({"content_type": content_type}, f)
                os.replace(temp_meta, meta_path)
            finally:
                if temp_meta.exists():
                    try:
                        temp_meta.unlink()
                    except Exception:
                        pass

        return clean_key

    def _sync_get(self, key: str) -> StoredFile:
        clean_key = validate_storage_key(key, self.storage_root)
        target_path = self.storage_root / clean_key
        if not target_path.is_file():
            raise StorageFileNotFoundError(f"File '{clean_key}' does not exist in local storage.")

        meta_path = target_path.parent / f"{target_path.name}.meta.json"
        content_type = self._detect_content_type(target_path, meta_path)

        with open(target_path, "rb") as f:
            content = f.read()

        return StoredFile(content=content, content_type=content_type)

    def _sync_delete(self, key: str) -> bool:
        clean_key = validate_storage_key(key, self.storage_root)
        target_path = self.storage_root / clean_key
        meta_path = target_path.parent / f"{target_path.name}.meta.json"
        try:
            if target_path.is_file():
                target_path.unlink()
            if meta_path.is_file():
                meta_path.unlink()
            return True
        except Exception as e:
            raise StorageError(f"Failed to delete local file '{clean_key}': {e}") from e

    def _sync_exists(self, key: str) -> bool:
        clean_key = validate_storage_key(key, self.storage_root)
        target_path = self.storage_root / clean_key
        return target_path.is_file()

    async def save_file(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None
    ) -> str:
        return await asyncio.to_thread(self._sync_save, key, content, content_type)

    async def get_file(self, key: str) -> StoredFile:
        return await asyncio.to_thread(self._sync_get, key)

    async def delete_file(self, key: str) -> bool:
        return await asyncio.to_thread(self._sync_delete, key)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._sync_exists, key)


class S3StorageService(BaseStorageService):
    """
    S3-compatible object storage adapter designed for Cloudflare R2.
    Uses boto3 with non-blocking asyncio.to_thread execution, preserves Content-Type
    metadata, and translates provider exceptions to unified StorageError types.
    """

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "auto",
        s3_client: Optional[Any] = None,
    ):
        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.region_name = region_name
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key

        if s3_client is not None:
            self._client = s3_client
        else:
            boto_config = botocore.config.Config(
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 3},
            )
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self.region_name,
                config=boto_config,
            )

    def _sync_save(self, key: str, content: bytes, content_type: Optional[str]) -> str:
        clean_key = validate_storage_key(key)
        kwargs = {
            "Bucket": self.bucket_name,
            "Key": clean_key,
            "Body": content,
        }
        if content_type:
            kwargs["ContentType"] = content_type
            kwargs["Metadata"] = {"content-type": content_type}

        try:
            self._client.put_object(**kwargs)
        except botocore.exceptions.ClientError as e:
            raise StorageError(f"Failed to save object to S3: {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error saving object to S3: {e}") from e

        return clean_key

    def _sync_get(self, key: str) -> StoredFile:
        clean_key = validate_storage_key(key)
        try:
            resp = self._client.get_object(Bucket=self.bucket_name, Key=clean_key)
        except botocore.exceptions.ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code in ("NoSuchKey", "404", "NotFound"):
                raise StorageFileNotFoundError(
                    f"Object '{clean_key}' not found in S3 bucket '{self.bucket_name}'."
                ) from e
            raise StorageError(f"Failed to retrieve object from S3: {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error retrieving object from S3: {e}") from e

        body_stream = resp.get("Body")
        try:
            body = body_stream.read() if body_stream is not None else b""
        finally:
            if body_stream is not None and hasattr(body_stream, "close"):
                try:
                    body_stream.close()
                except Exception:
                    pass

        content_type = resp.get("ContentType")
        if not content_type:
            metadata = resp.get("Metadata", {})
            content_type = metadata.get("content-type", "application/octet-stream")

        return StoredFile(content=body, content_type=content_type)

    def _sync_exists(self, key: str) -> bool:
        clean_key = validate_storage_key(key)
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code in ("NoSuchKey", "404", "NotFound"):
                return False
            raise StorageError(f"Failed checking object existence in S3: {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error checking object existence in S3: {e}") from e

    def _sync_delete(self, key: str) -> bool:
        clean_key = validate_storage_key(key)
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            # In S3/R2, delete_object returns 204 even if absent. If a provider returns 404/NoSuchKey,
            # the object is guaranteed absent, which satisfies idempotent deletion.
            if error_code in ("NoSuchKey", "404", "NotFound"):
                return True
            raise StorageError(f"Failed to delete object from S3: {e}") from e
        except Exception as e:
            raise StorageError(f"Unexpected error deleting object from S3: {e}") from e

    async def save_file(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None
    ) -> str:
        return await asyncio.to_thread(self._sync_save, key, content, content_type)

    async def get_file(self, key: str) -> StoredFile:
        return await asyncio.to_thread(self._sync_get, key)

    async def delete_file(self, key: str) -> bool:
        return await asyncio.to_thread(self._sync_delete, key)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._sync_exists, key)


@dataclass
class StorageConfig:
    """Configuration container for storage service initialization."""
    storage_backend: str = "local"
    local_storage_root: Optional[Path] = None
    s3_endpoint_url: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_region_name: str = "auto"

    @classmethod
    def from_env(cls) -> "StorageConfig":
        backend = os.getenv("STORAGE_BACKEND", "local").strip()
        custom_root = os.getenv("LOCAL_STORAGE_ROOT")
        root_path = Path(custom_root).resolve() if custom_root else None

        return cls(
            storage_backend=backend,
            local_storage_root=root_path,
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            s3_bucket_name=os.getenv("S3_BUCKET_NAME"),
            s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            s3_region_name=os.getenv("S3_REGION_NAME", "auto"),
        )


_cached_storage_service: Optional[BaseStorageService] = None
_cached_storage_config: Optional[StorageConfig] = None


def _create_storage_service(cfg: StorageConfig) -> BaseStorageService:
    backend = cfg.storage_backend.lower().strip()

    if backend == "local":
        return LocalStorageService(storage_root=cfg.local_storage_root)

    if backend == "s3":
        missing = []
        if not cfg.s3_endpoint_url:
            missing.append("S3_ENDPOINT_URL")
        if not cfg.s3_bucket_name:
            missing.append("S3_BUCKET_NAME")
        if not cfg.s3_access_key_id:
            missing.append("S3_ACCESS_KEY_ID")
        if not cfg.s3_secret_access_key:
            missing.append("S3_SECRET_ACCESS_KEY")

        if missing:
            raise StorageConfigurationError(
                f"S3 storage backend selected but missing required configuration parameters: {', '.join(missing)}"
            )

        return S3StorageService(
            endpoint_url=cfg.s3_endpoint_url,
            bucket_name=cfg.s3_bucket_name,
            access_key_id=cfg.s3_access_key_id,
            secret_access_key=cfg.s3_secret_access_key,
            region_name=cfg.s3_region_name or "auto",
        )

    raise StorageConfigurationError(
        f"Unsupported STORAGE_BACKEND '{cfg.storage_backend}'. Allowed backends: 'local', 's3'."
    )


def get_storage_service(config: Optional[StorageConfig] = None) -> BaseStorageService:
    """
    Factory function returning the configured storage service instance.
    Enforces strict configuration validation:
    - If STORAGE_BACKEND is 'local', initializes LocalStorageService.
    - If STORAGE_BACKEND is 's3', verifies all S3/R2 parameters and initializes S3StorageService.
    - Never silently falls back from 's3' to 'local'.
    - Never exposes secret values in exception messages.
    - Caches default instance for dependency lifecycle reuse.
    """
    global _cached_storage_service, _cached_storage_config

    if config is not None:
        return _create_storage_service(config)

    current_cfg = StorageConfig.from_env()
    if _cached_storage_service is not None and _cached_storage_config == current_cfg:
        return _cached_storage_service

    service = _create_storage_service(current_cfg)
    _cached_storage_service = service
    _cached_storage_config = current_cfg
    return _cached_storage_service


def reset_storage_service() -> None:
    """Resets the cached storage service instance. Intended for test isolation."""
    global _cached_storage_service, _cached_storage_config
    _cached_storage_service = None
    _cached_storage_config = None
