
import pytest

from app.document_ingestion import DocumentIngestion
from app.knowledge_versions import KnowledgeBaseVersions


def prepare_knowledge_base(tmp_path, filename, content):
    root = tmp_path / "knowledge_base"
    incoming = root / "incoming"
    incoming.mkdir(parents=True)

    document = incoming / filename
    document.write_text(content, encoding="utf-8")

    ingestion = DocumentIngestion(
        incoming_dir=incoming,
        quarantine_dir=root / "quarantine",
        manifest_path=root / "manifest.json",
    )
    ingestion.scan_and_process()

    versions = KnowledgeBaseVersions(root)
    return root, document, versions


def test_creates_version_snapshot(tmp_path):
    root, _, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "Password reset instructions"
    )

    version = versions.create_version()

    assert version["status"] == "candidate"
    assert "help.txt" in version["documents"]

    snapshot = (
        root
        / "versions"
        / version["version_id"]
        / "documents"
        / "help.txt"
    )

    assert snapshot.read_text(encoding="utf-8") == (
        "Password reset instructions"
    )


def test_activates_version(tmp_path):
    _, _, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "Password reset instructions"
    )

    version = versions.create_version()
    active = versions.activate_version(version["version_id"])

    assert active["active_version"] == version["version_id"]


def test_rolls_back_to_previous_version(tmp_path):
    root, document, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "First instructions"
    )

    first = versions.create_version()
    versions.activate_version(first["version_id"])

    document.write_text("Updated instructions", encoding="utf-8")

    # Re-run ingestion so the modified content is accepted.
    DocumentIngestion(
        root / "incoming",
        root / "quarantine",
        root / "manifest.json",
    ).scan_and_process()

    second = versions.create_version()
    versions.activate_version(second["version_id"])

    active = versions.rollback()

    assert active["active_version"] == first["version_id"]
    assert active["rollback"] is True


def test_rejects_snapshot_if_document_changed_after_ingestion(tmp_path):
    _, document, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "Original content"
    )

    document.write_text("Changed without re-ingestion", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after ingestion"):
        versions.create_version()


def test_rejects_missing_version(tmp_path):
    _, _, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "Instructions"
    )

    with pytest.raises(ValueError, match="does not exist"):
        versions.activate_version("unknown-version")


def test_rejects_rollback_without_previous_version(tmp_path):
    _, _, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "Instructions"
    )

    version = versions.create_version()
    versions.activate_version(version["version_id"])

    with pytest.raises(ValueError, match="No previous version"):
        versions.rollback()


def test_rejects_tampered_snapshot_during_activation(tmp_path):
    _, _, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "Original instructions"
    )

    version = versions.create_version()
    version_id = version["version_id"]

    snapshot_file = (
        versions.versions_dir
        / version_id
        / "documents"
        / "help.txt"
    )

    # Tamper with the snapshot after it was created.
    snapshot_file.write_text("Tampered instructions", encoding="utf-8")

    with pytest.raises(
        ValueError, match="Snapshot integrity check failed"
    ):
        versions.activate_version(version_id)


def test_rejects_corrupted_previous_snapshot_during_rollback(tmp_path):
    root, document, versions = prepare_knowledge_base(
        tmp_path, "help.txt", "First instructions"
    )

    # Create and activate the first version.
    first = versions.create_version()
    versions.activate_version(first["version_id"])

    # Update the document and ingest the new content.
    document.write_text("Second instructions", encoding="utf-8")

    DocumentIngestion(
        root / "incoming",
        root / "quarantine",
        root / "manifest.json",
    ).scan_and_process()

    # Create and activate the second version.
    second = versions.create_version()
    versions.activate_version(second["version_id"])

    # Corrupt the previous version's snapshot.
    previous_snapshot = (
        versions.versions_dir
        / first["version_id"]
        / "documents"
        / "help.txt"
    )

    previous_snapshot.write_text(
        "Corrupted previous instructions",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="Rollback snapshot integrity failed"
    ):
        versions.rollback()

    # The active version should remain the second version.
    active = versions._read_json(versions.active_path, {})
    assert active["active_version"] == second["version_id"]
