
from app.document_ingestion import DocumentIngestion


def create_ingestion(tmp_path):
    incoming = tmp_path / "incoming"
    quarantine = tmp_path / "quarantine"
    manifest = tmp_path / "manifest.json"

    return DocumentIngestion(
        incoming,
        quarantine,
        manifest,
    ), incoming, quarantine


def test_processes_new_document(tmp_path):
    ingestion, incoming, _ = create_ingestion(tmp_path)
    (incoming / "help.txt").write_text(
        "How to reset a password",
        encoding="utf-8",
    )

    result = ingestion.scan_and_process()

    assert result["results"][0]["status"] == "processed"


def test_skips_unchanged_document(tmp_path):
    ingestion, incoming, _ = create_ingestion(tmp_path)
    document = incoming / "help.txt"
    document.write_text("Reset your password", encoding="utf-8")

    assert ingestion.scan_and_process()["results"][0]["status"] == "processed"
    assert ingestion.scan_and_process()["results"][0]["status"] == "unchanged"


def test_processes_modified_document(tmp_path):
    ingestion, incoming, _ = create_ingestion(tmp_path)
    document = incoming / "help.txt"
    document.write_text("Old instructions", encoding="utf-8")
    ingestion.scan_and_process()

    document.write_text("Updated instructions", encoding="utf-8")
    result = ingestion.scan_and_process()

    assert result["results"][0]["status"] == "modified"


def test_detects_duplicate_content(tmp_path):
    ingestion, incoming, _ = create_ingestion(tmp_path)
    (incoming / "first.txt").write_text("Reset your password", encoding="utf-8")
    ingestion.scan_and_process()

    (incoming / "copy.txt").write_text(
        "  Reset   your password  ",
        encoding="utf-8",
    )
    result = ingestion.scan_and_process()

    duplicate = next(item for item in result["results"] if item["file"] == "copy.txt")
    assert duplicate["status"] == "duplicate"
    assert duplicate["duplicate_of"] == "first.txt"


def test_quarantines_unsupported_file(tmp_path):
    ingestion, incoming, quarantine = create_ingestion(tmp_path)
    (incoming / "malware.exe").write_bytes(b"not a supported document")

    result = ingestion.scan_and_process()

    assert result["results"][0]["status"] == "quarantined"
    assert (quarantine / "malware.exe").exists()
    assert not (incoming / "malware.exe").exists()


def test_quarantines_invalid_json(tmp_path):
    ingestion, incoming, quarantine = create_ingestion(tmp_path)
    (incoming / "broken.json").write_text(
        "{invalid json",
        encoding="utf-8",
    )

    result = ingestion.scan_and_process()

    assert result["results"][0]["status"] == "quarantined"
    assert (quarantine / "broken.json").exists()
