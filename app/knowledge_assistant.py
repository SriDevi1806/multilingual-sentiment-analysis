
import json
import re
from datetime import date, datetime
from pathlib import Path

from app.knowledge_security import scan_prompt_injection


ROLE_LEVELS = {
    "viewer": 1,
    "contributor": 2,
    "approver": 3,
    "admin": 4,
}

ACCESS_LEVELS = {
    "public": 0,
    "viewer": 1,
    "contributor": 2,
    "approver": 3,
    "restricted": 3,
    "admin": 4,
}

DEFAULT_METADATA = {
    "version": "unversioned",
    "product": "*",
    "region": "*",
    "access_level": "public",
    "effective_date": "1970-01-01",
    "expiry_date": None,
    "document_type": "general",
    "policy_id": None,
}


def _parse_date(value, field_name, allow_none=False):
    """Parse and validate a date."""
    if value is None or value == "":
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required")

    if isinstance(value, datetime):
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        )

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        )

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        ) from exc

    if parsed.isoformat() != value:
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        )

    return parsed


def _parse_front_matter(text):
    """Read simple YAML-style key: value Markdown front matter."""
    if not text.startswith("---\n"):
        return {}, text

    parts = text.split("\n---", 1)

    if len(parts) != 2:
        return {}, text

    metadata = {}

    for line in parts[0][4:].splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")

        if key:
            metadata[key] = value or None

    body = parts[1].lstrip("\r\n")
    return metadata, body


def _read_document(path, default_version):
    """Read a document and validate its metadata."""
    raw = path.read_text(encoding="utf-8-sig")
    metadata = {}
    content = raw

    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON document: {path.name}"
            ) from exc

        if isinstance(payload, dict):
            embedded_metadata = payload.get("metadata", {})

            if not isinstance(embedded_metadata, dict):
                raise ValueError(
                    f"Invalid embedded metadata in {path.name}"
                )

            metadata.update(embedded_metadata)

            body = payload.get(
                "content",
                payload.get("text"),
            )

            if not isinstance(body, str):
                raise ValueError(
                    "JSON document must contain string "
                    f"content or text: {path.name}"
                )

            content = body

        elif isinstance(payload, str):
            content = payload

        else:
            content = raw

    if path.suffix.lower() == ".md":
        front_metadata, body = _parse_front_matter(raw)
        metadata.update(front_metadata)
        content = body

    # Sidecar metadata takes precedence over embedded metadata.
    sidecar = path.with_name(
        path.name + ".metadata.json"
    )

    if sidecar.is_file() and not sidecar.is_symlink():
        try:
            sidecar_metadata = json.loads(
                sidecar.read_text(encoding="utf-8")
            )
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise ValueError(
                f"Invalid metadata sidecar: {sidecar.name}"
            ) from exc

        if not isinstance(sidecar_metadata, dict):
            raise ValueError(
                "Metadata sidecar must contain a JSON object: "
                f"{sidecar.name}"
            )

        metadata.update(sidecar_metadata)

    result = dict(DEFAULT_METADATA)
    result.update(metadata)

    version = metadata.get("version") or default_version

    if not isinstance(version, str) or not version.strip():
        raise ValueError(
            f"Invalid version in {path.name}"
        )

    result["version"] = version

    access_level = result.get("access_level")

    if (
        not isinstance(access_level, str)
        or access_level not in ACCESS_LEVELS
    ):
        raise ValueError(
            f"Invalid access_level in {path.name}"
        )

    for field in ("product", "region", "version"):
        value = result.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Invalid {field} in {path.name}"
            )

    for field in ("document_type", "policy_id"):
        value = result.get(field)

        if value is not None and (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"Invalid {field} in {path.name}"
            )

    result["effective_date"] = _parse_date(
        result.get("effective_date"),
        "effective_date",
    )

    result["expiry_date"] = _parse_date(
        result.get("expiry_date"),
        "expiry_date",
        allow_none=True,
    )

    if (
        result["expiry_date"] is not None
        and result["expiry_date"] < result["effective_date"]
    ):
        raise ValueError(
            f"expiry_date precedes effective_date in {path.name}"
        )

    return {
        "filename": path.name,
        "content": content,
        "metadata": result,
    }


def load_knowledge_documents(
    documents_dir,
    version="unversioned",
):
    """Load supported knowledge documents from a directory."""
    root = Path(documents_dir)

    if not root.is_dir() or root.is_symlink():
        raise ValueError(
            "Documents directory does not exist"
        )

    documents = []

    for path in sorted(root.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue

        if path.name.endswith(".metadata.json"):
            continue

        if path.suffix.lower() not in {
            ".txt",
            ".md",
            ".json",
            ".csv",
        }:
            continue

        documents.append(
            _read_document(path, version)
        )

    if not documents:
        raise ValueError(
            "No readable knowledge documents found"
        )

    return documents


def _tokens(text):
    """Extract Unicode word tokens for multilingual matching."""
    return set(
        re.findall(
            r"[^\W_]+",
            text.casefold(),
            flags=re.UNICODE,
        )
    )


def _sentences(text):
    """Split text into candidate sentences."""
    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+|\n+",
            text,
        )
        if sentence.strip()
    ]


class KnowledgeAssistant:
    """Metadata-aware, evidence-grounded knowledge retrieval."""

    def __init__(
        self,
        documents_dir,
        version="unversioned",
    ):
        self.documents_dir = Path(documents_dir)
        self.version = version

    @staticmethod
    def _authorized(metadata, role):
        """Check whether a role can access a document."""
        if (
            not isinstance(role, str)
            or role not in ROLE_LEVELS
        ):
            return False

        required = ACCESS_LEVELS[metadata["access_level"]]
        return ROLE_LEVELS[role] >= required

    @staticmethod
    def _matches_scope(metadata, product, region):
        """Check product and regional applicability safely."""
        if product is not None and (
            not isinstance(product, str)
            or not product.strip()
        ):
            return False

        if region is not None and (
            not isinstance(region, str)
            or not region.strip()
        ):
            return False

        def matches(value, requested):
            return (
                requested is None
                or value == "*"
                or value.casefold() == requested.casefold()
            )

        return (
            matches(metadata["product"], product)
            and matches(metadata["region"], region)
        )

    @staticmethod
    def _is_active(metadata, target_date):
        """Check whether a document applies on the requested date."""
        start = metadata["effective_date"]
        end = metadata["expiry_date"]

        # Expiry date is inclusive.
        return (
            start <= target_date
            and (end is None or target_date <= end)
        )

    def answer(
        self,
        question,
        role="viewer",
        product=None,
        region=None,
        as_of_date=None,
    ):
        """Answer using permitted evidence or safely abstain."""
        if (
            not isinstance(question, str)
            or not question.strip()
        ):
            return {
                "status": "clarification_required",
                "answer": "Please provide a question.",
                "citations": [],
            }

        if (
            not isinstance(role, str)
            or role not in ROLE_LEVELS
        ):
            return {
                "status": "refused",
                "answer": (
                    "Your role is not authorized to query "
                    "this knowledge base."
                ),
                "citations": [],
            }

        # Validate scope inputs before loading or searching documents.
        if product is not None and (
            not isinstance(product, str)
            or not product.strip()
        ):
            return {
                "status": "clarification_required",
                "answer": "Please provide a valid product name.",
                "citations": [],
            }

        if region is not None and (
            not isinstance(region, str)
            or not region.strip()
        ):
            return {
                "status": "clarification_required",
                "answer": "Please provide a valid region.",
                "citations": [],
            }

        try:
            target_date = _parse_date(
                date.today() if as_of_date is None else as_of_date,
                "as_of_date",
            )

            documents = load_knowledge_documents(
                self.documents_dir,
                self.version,
            )

        except (ValueError, TypeError, OSError) as exc:
            return {
                "status": "refused",
                "answer": (
                    "Knowledge documents could not be loaded safely. "
                    "Please contact the system administrator."
                ),
                "citations": [],
            }

        question_terms = _tokens(question)

        if not question_terms:
            return {
                "status": "clarification_required",
                "answer": (
                    "Please clarify what information you need."
                ),
                "citations": [],
            }

        # Step 1: Apply authorization, scope, and date filters.
        eligible_documents = []

        for document in documents:
            metadata = document["metadata"]

            if not self._authorized(metadata, role):
                continue

            if not self._matches_scope(
                metadata,
                product,
                region,
            ):
                continue

            if not self._is_active(metadata, target_date):
                continue

            eligible_documents.append(document)

        # Step 2: Select the latest applicable policy date BEFORE
        # matching sentences, preventing fallback to older policies.
        latest_policy_dates = {}

        for document in eligible_documents:
            metadata = document["metadata"]
            policy_id = metadata.get("policy_id")

            if not policy_id:
                continue

            effective = metadata["effective_date"]
            previous = latest_policy_dates.get(policy_id)

            if previous is None or effective > previous:
                latest_policy_dates[policy_id] = effective

        # Step 3: Search only the latest applicable version of each
        # identified policy. Documents without policy_id remain eligible.
        candidates = []

        for document in eligible_documents:
            metadata = document["metadata"]
            policy_id = metadata.get("policy_id")

            if (
                policy_id
                and metadata["effective_date"]
                != latest_policy_dates[policy_id]
            ):
                continue

            content = document["content"]

            # Fail closed if the scanner flags a document or fails.
            try:
                scan = scan_prompt_injection(content)

                if scan.suspicious:
                    continue
            except Exception:
                continue

            for sentence in _sentences(content):
                terms = _tokens(sentence)
                overlap = question_terms & terms

                if not overlap:
                    continue

                score = len(overlap) / len(question_terms)

                candidates.append({
                    "sentence": sentence,
                    "score": score,
                    "filename": document["filename"],
                    "metadata": metadata,
                    "overlap": overlap,
                })

        if not candidates:
            return {
                "status": "insufficient_evidence",
                "answer": (
                    "I couldn't find sufficient authorized, applicable "
                    "evidence to answer that question. Please clarify the "
                    "product, region, or relevant policy date if applicable."
                ),
                "citations": [],
            }

        # Step 4: Rank the matching evidence.
        candidates.sort(
            key=lambda item: (
                item["score"],
                item["metadata"]["effective_date"],
            ),
            reverse=True,
        )

        best = candidates[0]

        # Step 5: Avoid guessing when equally relevant statements differ.
        tied = [
            item
            for item in candidates
            if item["score"] == best["score"]
        ]

        distinct_answers = {
            item["sentence"].strip().casefold()
            for item in tied
        }

        if len(distinct_answers) > 1:
            return {
                "status": "clarification_required",
                "answer": (
                    "I found multiple equally relevant statements and "
                    "cannot determine a reliable answer. Please clarify "
                    "the policy or topic you mean."
                ),
                "citations": [],
            }

        # Step 6: Return the answer with its citation.
        metadata = best["metadata"]

        citation = {
            "source": best["filename"],
            "version": metadata["version"],
            "product": metadata["product"],
            "region": metadata["region"],
            "effective_date": (
                metadata["effective_date"].isoformat()
            ),
            "expiry_date": (
                metadata["expiry_date"].isoformat()
                if metadata["expiry_date"] is not None
                else None
            ),
        }

        return {
            "status": "answered",
            "answer": best["sentence"],
            "citations": [citation],
        }
