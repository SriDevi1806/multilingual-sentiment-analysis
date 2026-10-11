
import json
import re
from pathlib import Path


def normalize_text(text):
    """Normalize text for deterministic answer comparisons."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def tokenize(text):
    return set(normalize_text(text).split())


def load_documents(version_dir):
    """Load text documents from a knowledge-base version snapshot."""
    documents_dir = Path(version_dir) / "documents"

    if not documents_dir.is_dir():
        raise ValueError("Version documents directory does not exist")

    documents = {}

    for path in sorted(documents_dir.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue

        if path.suffix.lower() not in {".txt", ".md", ".json", ".csv"}:
            continue

        try:
            documents[path.name] = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Invalid UTF-8 document: {path.name}"
            ) from exc

    if not documents:
        raise ValueError("Version contains no readable documents")

    return documents


def split_sentences(text):
    """Simple sentence splitting for the initial retrieval baseline."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    return [sentence.strip() for sentence in sentences if sentence.strip()]


def retrieve_answer(question, documents):
    """Return the document sentence with the best question-term overlap."""
    question_terms = tokenize(question)

    if not question_terms:
        return ""

    best_answer = ""
    best_score = 0

    for content in documents.values():
        for sentence in split_sentences(content):
            sentence_terms = tokenize(sentence)
            score = len(question_terms & sentence_terms)

            if score > best_score:
                best_score = score
                best_answer = sentence

    # Avoid inventing an answer when no question terms match.
    return best_answer if best_score > 0 else ""


class KnowledgeQualityGate:
    """Evaluate candidate answer accuracy and document grounding."""

    def __init__(
        self,
        min_accuracy=0.80,
        min_grounding=0.90,
        max_accuracy_drop=0.05,
        max_grounding_drop=0.05,
    ):
        for name, value in {
            "min_accuracy": min_accuracy,
            "min_grounding": min_grounding,
            "max_accuracy_drop": max_accuracy_drop,
            "max_grounding_drop": max_grounding_drop,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")

        self.min_accuracy = min_accuracy
        self.min_grounding = min_grounding
        self.max_accuracy_drop = max_accuracy_drop
        self.max_grounding_drop = max_grounding_drop

    @staticmethod
    def _evaluate_documents(documents, test_cases):
        if not test_cases:
            raise ValueError("At least one quality test case is required")

        correct = 0
        grounded = 0
        results = []

        corpus = "\n".join(documents.values())
        corpus_normalized = normalize_text(corpus)

        for case in test_cases:
            question = case.get("question", "").strip()
            expected = case.get("expected_answer", "").strip()

            if not question or not expected:
                raise ValueError(
                    "Each test case needs a question and expected_answer"
                )

            answer = retrieve_answer(question, documents)

            # Exact normalized matching is intentionally conservative.
            is_correct = (
                normalize_text(answer) == normalize_text(expected)
            )

            # Grounding requires the returned answer to be present
            # in the candidate's source documents.
            is_grounded = bool(answer) and (
                normalize_text(answer) in corpus_normalized
            )

            correct += int(is_correct)
            grounded += int(is_grounded)

            results.append({
                "question": question,
                "answer": answer,
                "correct": is_correct,
                "grounded": is_grounded,
            })

        count = len(test_cases)

        return {
            "accuracy": correct / count,
            "grounding": grounded / count,
            "total_cases": count,
            "results": results,
        }

    def evaluate(
        self,
        candidate_version_dir,
        test_cases,
        baseline_version_dir=None,
    ):
        """
        Evaluate a candidate and optionally compare it with a baseline.

        A candidate is approved only when absolute thresholds and
        regression limits pass.
        """
        candidate_documents = load_documents(candidate_version_dir)

        candidate_metrics = self._evaluate_documents(
            candidate_documents,
            test_cases,
        )

        baseline_metrics = None
        if baseline_version_dir is not None:
            baseline_documents = load_documents(baseline_version_dir)
            baseline_metrics = self._evaluate_documents(
                baseline_documents,
                test_cases,
            )

        reasons = []

        if candidate_metrics["accuracy"] < self.min_accuracy:
            reasons.append("Accuracy below minimum threshold")

        if candidate_metrics["grounding"] < self.min_grounding:
            reasons.append("Grounding below minimum threshold")

        if baseline_metrics is not None:
            accuracy_drop = (
                baseline_metrics["accuracy"]
                - candidate_metrics["accuracy"]
            )
            grounding_drop = (
                baseline_metrics["grounding"]
                - candidate_metrics["grounding"]
            )

            if accuracy_drop > self.max_accuracy_drop:
                reasons.append("Accuracy regression exceeds allowed limit")

            if grounding_drop > self.max_grounding_drop:
                reasons.append("Grounding regression exceeds allowed limit")
        else:
            accuracy_drop = None
            grounding_drop = None

        return {
            "status": "approved" if not reasons else "rejected",
            "approved": not reasons,
            "reasons": reasons,
            "candidate": {
                "accuracy": candidate_metrics["accuracy"],
                "grounding": candidate_metrics["grounding"],
                "total_cases": candidate_metrics["total_cases"],
            },
            "baseline": baseline_metrics,
            "accuracy_drop": accuracy_drop,
            "grounding_drop": grounding_drop,
            "results": candidate_metrics["results"],
        }
