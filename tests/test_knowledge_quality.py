
import pytest

from app.knowledge_quality import KnowledgeQualityGate, load_documents



def make_version(tmp_path, name, content):
    version_dir = tmp_path / name
    documents_dir = version_dir / "documents"
    documents_dir.mkdir(parents=True)

    (documents_dir / "help.txt").write_text(
        content,
        encoding="utf-8",
    )

    return version_dir


def test_approves_correct_grounded_answers(tmp_path):
    candidate = make_version(
        tmp_path,
        "candidate",
        "To reset your password, open Settings and select Reset Password.",
    )

    cases = [{
        "question": "How do I reset my password?",
        "expected_answer": (
            "To reset your password, open Settings and select Reset Password."
        ),
    }]

    report = KnowledgeQualityGate().evaluate(candidate, cases)

    assert report["approved"] is True
    assert report["candidate"]["accuracy"] == 1.0
    assert report["candidate"]["grounding"] == 1.0


def test_rejects_incorrect_expected_answer(tmp_path):
    candidate = make_version(
        tmp_path,
        "candidate",
        "To reset your password, open Settings and select Reset Password.",
    )

    cases = [{
        "question": "How do I reset my password?",
        "expected_answer": "Contact the billing department.",
    }]

    report = KnowledgeQualityGate().evaluate(candidate, cases)

    assert report["approved"] is False
    assert "Accuracy below minimum threshold" in report["reasons"]


def test_rejects_empty_retrieval_for_unmatched_question(tmp_path):
    candidate = make_version(
        tmp_path,
        "candidate",
        "The office cafeteria serves lunch at noon.",
    )

    cases = [{
        "question": "How do I reset my password?",
        "expected_answer": "Open Settings and select Reset Password.",
    }]

    report = KnowledgeQualityGate().evaluate(candidate, cases)

    assert report["approved"] is False
    assert report["candidate"]["grounding"] == 0.0


def test_rejects_candidate_with_accuracy_regression(tmp_path):
    baseline = make_version(
        tmp_path,
        "baseline",
        "Password reset: open Settings and select Reset Password. "
        "Billing support: contact the billing department.",
    )

    candidate = make_version(
        tmp_path,
        "candidate",
        "Password reset: open Settings and select Reset Password. "
        "Billing support: contact the sales department.",
    )

    cases = [
        {
            "question": "How do I reset my password?",
            "expected_answer": (
                "Password reset: open Settings and select Reset Password."
            ),
        },
        {
            "question": "How do I contact billing support?",
            "expected_answer": (
                "Billing support: contact the billing department."
            ),
        },
    ]

    report = KnowledgeQualityGate(
        min_accuracy=0.5,
        max_accuracy_drop=0.0,
    ).evaluate(candidate, cases, baseline)

    assert report["approved"] is False
    assert "Accuracy regression exceeds allowed limit" in report["reasons"]


def test_rejects_missing_documents_directory(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        KnowledgeQualityGate().evaluate(
            tmp_path / "missing",
            [{"question": "Test?", "expected_answer": "Answer"}],
        )


def test_requires_test_cases(tmp_path):
    candidate = make_version(
        tmp_path,
        "candidate",
        "General support information.",
    )

    with pytest.raises(ValueError, match="At least one"):
        KnowledgeQualityGate().evaluate(candidate, [])



def test_metadata_sidecar_is_not_loaded_as_document(tmp_path):
    version_dir = make_version(
        tmp_path,
        "candidate",
        "Refund requests must be submitted within 30 days.",
    )
    documents_dir = version_dir / "documents"

    (documents_dir / "help.txt.metadata.json").write_text(
        '{"product": "payments", "region": "IN"}',
        encoding="utf-8",
    )

    documents = load_documents(version_dir)

    assert list(documents) == ["help.txt"]
    assert "30 days" in documents["help.txt"]