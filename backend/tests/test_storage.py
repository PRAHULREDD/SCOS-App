"""
Unit tests for SCOS Storage Abstraction Layer (Phase 6.1)

Verifies:
1. LocalStorageService: atomic writes, isolation in tmp_path, path traversal rejection,
   content-type preservation, existence, deletion, missing file handling.
2. S3StorageService: S3/R2 adapter operations using botocore.stub.Stubber for 100% offline testing.
3. Factory & Configuration: provider selection, strict validation, missing parameter errors.
"""
import io
import sys
from pathlib import Path
import pytest
import boto3
from botocore.stub import Stubber

# Ensure backend root is on sys.path regardless of execution working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.storage_service import (
    LocalStorageService,
    S3StorageService,
    StorageConfig,
    StoredFile,
    StorageError,
    StorageFileNotFoundError,
    StorageConfigurationError,
    StoragePathTraversalError,
    get_storage_service,
    reset_storage_service,
    validate_storage_key,
)


# ============================================================================
# 1. LocalStorageService Tests
# ============================================================================

@pytest.mark.asyncio
async def test_local_save_and_retrieve_success(tmp_path: Path):
    """Saves file to isolated tmp_path and retrieves content and content_type."""
    service = LocalStorageService(storage_root=tmp_path)
    content = b"fake-jpeg-bytes"
    key = "tasks/task_1.jpg"

    saved_key = await service.save_file(key, content, content_type="image/jpeg")
    assert saved_key == "tasks/task_1.jpg"

    stored = await service.get_file(saved_key)
    assert isinstance(stored, StoredFile)
    assert stored.content == content
    assert stored.content_type == "image/jpeg"

    # Verify tuple unpacking
    unpacked_content, unpacked_type = stored
    assert unpacked_content == content
    assert unpacked_type == "image/jpeg"

    # Verify to_stream()
    stream = stored.to_stream()
    assert isinstance(stream, io.BytesIO)
    assert stream.read() == content


@pytest.mark.asyncio
async def test_local_preserve_custom_content_type(tmp_path: Path):
    """Preserves arbitrary custom Content-Type for extensionless keys via metadata sidecar."""
    service = LocalStorageService(storage_root=tmp_path)
    content = b"custom binary data"
    key = "proofs/tasks/100"

    await service.save_file(key, content, content_type="application/x-custom-proof")

    stored = await service.get_file(key)
    assert stored.content == content
    assert stored.content_type == "application/x-custom-proof"


@pytest.mark.asyncio
async def test_local_content_type_inferred_from_extension(tmp_path: Path):
    """Infers standard image content types from file extension when no metadata is passed."""
    service = LocalStorageService(storage_root=tmp_path)
    content = b"dummy png content"
    key = "images/photo.png"

    await service.save_file(key, content)
    stored = await service.get_file(key)
    assert stored.content == content
    assert stored.content_type == "image/png"


@pytest.mark.asyncio
async def test_local_content_type_inferred_from_magic_bytes(tmp_path: Path):
    """Infers image/jpeg from JPEG magic bytes when extensionless and no metadata passed."""
    service = LocalStorageService(storage_root=tmp_path)
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIFtest"
    key = "images/raw_blob"

    await service.save_file(key, jpeg_bytes)
    stored = await service.get_file(key)
    assert stored.content == jpeg_bytes
    assert stored.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_local_exists(tmp_path: Path):
    """Tests existence check for present and missing local keys."""
    service = LocalStorageService(storage_root=tmp_path)
    key = "checks/item.txt"

    assert await service.exists(key) is False
    await service.save_file(key, b"hello", content_type="text/plain")
    assert await service.exists(key) is True


@pytest.mark.asyncio
async def test_local_delete_file(tmp_path: Path):
    """Deletes existing file and associated metadata sidecar; idempotent deletion returns True when absent."""
    service = LocalStorageService(storage_root=tmp_path)
    key = "delete_me.jpg"

    await service.save_file(key, b"to-delete", content_type="image/jpeg")
    assert await service.exists(key) is True

    deleted = await service.delete_file(key)
    assert deleted is True
    assert await service.exists(key) is False

    # Second delete on already-absent file idempotently succeeds
    assert await service.delete_file(key) is True


@pytest.mark.asyncio
async def test_local_missing_file_raises_storage_not_found(tmp_path: Path):
    """Attempting to get a non-existent file raises StorageFileNotFoundError."""
    service = LocalStorageService(storage_root=tmp_path)
    with pytest.raises(StorageFileNotFoundError) as exc_info:
        await service.get_file("does_not_exist.jpg")

    assert issubclass(StorageFileNotFoundError, StorageError)
    assert issubclass(StorageFileNotFoundError, FileNotFoundError)
    assert "does not exist in local storage" in str(exc_info.value)


@pytest.mark.asyncio
async def test_local_reject_path_traversal(tmp_path: Path):
    """Rejects path traversal attempts across save, get, delete, and exists."""
    service = LocalStorageService(storage_root=tmp_path)
    malicious_keys = [
        "../secret.txt",
        "..\\windows\\secret.txt",
        "/absolute/path/file.jpg",
        "nested/../../outside.txt",
        "",
        "   ",
        "valid/path/\0nullbyte.txt",
    ]

    for bad_key in malicious_keys:
        with pytest.raises(StoragePathTraversalError):
            await service.save_file(bad_key, b"data")

        with pytest.raises(StoragePathTraversalError):
            await service.get_file(bad_key)

        with pytest.raises(StoragePathTraversalError):
            await service.delete_file(bad_key)

        with pytest.raises(StoragePathTraversalError):
            await service.exists(bad_key)


@pytest.mark.asyncio
async def test_local_nested_keys_and_directory_creation(tmp_path: Path):
    """Automatically creates parent directories for nested keys."""
    service = LocalStorageService(storage_root=tmp_path)
    key = "zone_1/drivers/4/tasks/88/proof.webp"
    content = b"webp-data"

    saved_key = await service.save_file(key, content, content_type="image/webp")
    assert saved_key == key

    stored = await service.get_file(key)
    assert stored.content == content
    assert stored.content_type == "image/webp"

    expected_disk_path = tmp_path / "zone_1" / "drivers" / "4" / "tasks" / "88" / "proof.webp"
    assert expected_disk_path.is_file()


@pytest.mark.asyncio
async def test_local_isolation_from_application_uploads(tmp_path: Path):
    """Ensures test operations only write into tmp_path and never touch backend/uploads/proof_photos/."""
    service = LocalStorageService(storage_root=tmp_path)
    app_uploads = Path("backend/uploads/proof_photos").resolve()
    initial_app_count = len(list(app_uploads.glob("*"))) if app_uploads.exists() else 0

    await service.save_file("isolation_test.jpg", b"isolated", content_type="image/jpeg")

    # Verify written to tmp_path
    assert (tmp_path / "isolation_test.jpg").is_file()

    # Verify app_uploads count was untouched
    if app_uploads.exists():
        final_app_count = len(list(app_uploads.glob("*")))
        assert final_app_count == initial_app_count


# ============================================================================
# 2. S3StorageService Tests (Mocked with botocore Stubber)
# ============================================================================

@pytest.fixture
def s3_stub():
    """Provides a mocked S3 client with botocore Stubber activated."""
    client = boto3.client(
        "s3",
        region_name="auto",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
        endpoint_url="https://mock.r2.cloudflarestorage.com",
    )
    stubber = Stubber(client)
    stubber.activate()
    yield client, stubber
    stubber.deactivate()


@pytest.mark.asyncio
async def test_s3_save_file_with_metadata(s3_stub):
    """Verifies put_object dispatch with body, content-type, and metadata."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    key = "proofs/tasks/1.jpg"
    content = b"s3-jpeg-bytes"

    expected_params = {
        "Bucket": "test-bucket",
        "Key": key,
        "Body": content,
        "ContentType": "image/jpeg",
        "Metadata": {"content-type": "image/jpeg"},
    }
    stubber.add_response("put_object", {"ETag": '"mock-etag"'}, expected_params)

    saved_key = await service.save_file(key, content, content_type="image/jpeg")
    assert saved_key == key
    stubber.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_s3_get_file_success(s3_stub):
    """Verifies get_object retrieval and ContentType parsing."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    key = "proofs/tasks/2.png"
    content = b"s3-png-bytes"

    expected_params = {"Bucket": "test-bucket", "Key": key}
    service_response = {
        "Body": io.BytesIO(content),
        "ContentType": "image/png",
    }
    stubber.add_response("get_object", service_response, expected_params)

    stored = await service.get_file(key)
    assert stored.content == content
    assert stored.content_type == "image/png"
    stubber.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_s3_get_file_missing_object_raises_not_found(s3_stub):
    """Translates S3 NoSuchKey / 404 ClientError to StorageFileNotFoundError."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    key = "proofs/missing.jpg"
    stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        service_message="The specified key does not exist.",
        http_status_code=404,
        expected_params={"Bucket": "test-bucket", "Key": key},
    )

    with pytest.raises(StorageFileNotFoundError) as exc_info:
        await service.get_file(key)

    assert "not found in S3 bucket" in str(exc_info.value)
    stubber.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_s3_exists_true_and_false(s3_stub):
    """Verifies head_object returning True on success and False on 404."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    # 1. Existing key
    stubber.add_response(
        "head_object",
        {"ContentLength": 100, "ContentType": "image/jpeg"},
        {"Bucket": "test-bucket", "Key": "present.jpg"},
    )
    assert await service.exists("present.jpg") is True

    # 2. Missing key
    stubber.add_client_error(
        "head_object",
        service_error_code="404",
        service_message="Not Found",
        http_status_code=404,
        expected_params={"Bucket": "test-bucket", "Key": "missing.jpg"},
    )
    assert await service.exists("missing.jpg") is False

    stubber.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_s3_delete_file(s3_stub):
    """Verifies realistic S3 idempotent deletion: native 204 or absent key returns True; provider error raises StorageError."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    # Case A: Standard S3 deletion of existing object returns empty 200/204 -> True
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": "test-bucket", "Key": "existing.jpg"},
    )
    assert await service.delete_file("existing.jpg") is True

    # Case B: Standard S3 deletion of non-existent object also returns empty 200/204 -> True (idempotent)
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": "test-bucket", "Key": "non_existent.jpg"},
    )
    assert await service.delete_file("non_existent.jpg") is True

    # Case C: S3 provider returning 404 / NoSuchKey also satisfies idempotent absence -> True
    stubber.add_client_error(
        "delete_object",
        service_error_code="NoSuchKey",
        service_message="Not found",
        http_status_code=404,
        expected_params={"Bucket": "test-bucket", "Key": "already_absent.jpg"},
    )
    assert await service.delete_file("already_absent.jpg") is True

    # Case D: Server error / AccessDenied raises StorageError
    stubber.add_client_error(
        "delete_object",
        service_error_code="InternalError",
        service_message="S3 service outage",
        http_status_code=500,
        expected_params={"Bucket": "test-bucket", "Key": "server_error.jpg"},
    )
    with pytest.raises(StorageError):
        await service.delete_file("server_error.jpg")

    stubber.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_s3_provider_error_handling(s3_stub):
    """Translates generic/server S3 ClientErrors to StorageError (not FileNotFoundError)."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    key = "err_test.jpg"
    stubber.add_client_error(
        "get_object",
        service_error_code="InternalError",
        service_message="We encountered an internal error. Please try again.",
        http_status_code=500,
        expected_params={"Bucket": "test-bucket", "Key": key},
    )

    with pytest.raises(StorageError) as exc_info:
        await service.get_file(key)

    assert not isinstance(exc_info.value, StorageFileNotFoundError)
    assert "Failed to retrieve object from S3" in str(exc_info.value)
    stubber.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_s3_reject_path_traversal(s3_stub):
    """Rejects path traversal before any network dispatch to S3."""
    client, _ = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    with pytest.raises(StoragePathTraversalError):
        await service.save_file("../escape.jpg", b"data")


# ============================================================================
# 3. Factory & Configuration Tests
# ============================================================================

def test_factory_default_local(tmp_path: Path):
    """Factory returns LocalStorageService by default."""
    cfg = StorageConfig(storage_backend="local", local_storage_root=tmp_path)
    service = get_storage_service(cfg)
    assert isinstance(service, LocalStorageService)
    assert service.storage_root == tmp_path.resolve()


def test_factory_s3_success():
    """Factory initializes S3StorageService when all required parameters are present."""
    cfg = StorageConfig(
        storage_backend="s3",
        s3_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_bucket_name="my-bucket",
        s3_access_key_id="my-key",
        s3_secret_access_key="my-secret",
        s3_region_name="auto",
    )
    service = get_storage_service(cfg)
    assert isinstance(service, S3StorageService)
    assert service.bucket_name == "my-bucket"
    assert service.endpoint_url == "https://account.r2.cloudflarestorage.com"


def test_factory_s3_missing_parameters_raises_config_error():
    """Factory raises StorageConfigurationError listing missing variables without exposing secrets."""
    cfg = StorageConfig(
        storage_backend="s3",
        s3_endpoint_url="https://account.r2.cloudflarestorage.com",
        # Missing bucket, access_key, secret_key
    )
    with pytest.raises(StorageConfigurationError) as exc_info:
        get_storage_service(cfg)

    err_msg = str(exc_info.value)
    assert "S3_BUCKET_NAME" in err_msg
    assert "S3_ACCESS_KEY_ID" in err_msg
    assert "S3_SECRET_ACCESS_KEY" in err_msg
    # Ensure no secrets leaked
    assert "my-secret" not in err_msg


def test_factory_unsupported_backend():
    """Factory rejects unsupported storage backends."""
    cfg = StorageConfig(storage_backend="gcs_unsupported")
    with pytest.raises(StorageConfigurationError) as exc_info:
        get_storage_service(cfg)
    assert "Unsupported STORAGE_BACKEND 'gcs_unsupported'" in str(exc_info.value)


def test_config_from_env(monkeypatch):
    """StorageConfig reads from environment variables accurately."""
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://env.r2.cloudflarestorage.com")
    monkeypatch.setenv("S3_BUCKET_NAME", "env-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "env-key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "env-secret")
    monkeypatch.setenv("S3_REGION_NAME", "us-east-1")

    cfg = StorageConfig.from_env()
    assert cfg.storage_backend == "s3"
    assert cfg.s3_endpoint_url == "https://env.r2.cloudflarestorage.com"
    assert cfg.s3_bucket_name == "env-bucket"
    assert cfg.s3_access_key_id == "env-key"
    assert cfg.s3_secret_access_key == "env-secret"
    assert cfg.s3_region_name == "us-east-1"


@pytest.mark.asyncio
async def test_s3_streaming_body_closure(s3_stub):
    """Verifies that StreamingBody.close() is called after reading object."""
    client, stubber = s3_stub
    service = S3StorageService(
        endpoint_url="https://mock.r2.cloudflarestorage.com",
        bucket_name="test-bucket",
        access_key_id="test_key",
        secret_access_key="test_secret",
        s3_client=client,
    )

    class MockStreamingBody(io.BytesIO):
        def __init__(self, data: bytes):
            super().__init__(data)
            self.closed_called = False

        def close(self):
            self.closed_called = True
            super().close()

    mock_body = MockStreamingBody(b"streamed-data")
    stubber.add_response(
        "get_object",
        {"Body": mock_body, "ContentType": "image/jpeg"},
        {"Bucket": "test-bucket", "Key": "stream_test.jpg"},
    )

    stored = await service.get_file("stream_test.jpg")
    assert stored.content == b"streamed-data"
    assert mock_body.closed_called is True


def test_factory_caching_and_reset(monkeypatch, tmp_path):
    """Verifies factory caches service singleton and reset_storage_service clears it."""
    reset_storage_service()
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))

    svc1 = get_storage_service()
    svc2 = get_storage_service()
    assert svc1 is svc2

    reset_storage_service()
    svc3 = get_storage_service()
    assert svc3 is not svc1
    reset_storage_service()
