from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from app.common.redaction import REDACTED, redact_sensitive
from app.devices.repository import DeviceRepository
from app.netconf.services import NetconfOperationResult
from app.storage.models import DeviceConfigSnapshot

ROLLBACK_NORMALIZED_CONTENT_MAX_BYTES = 4 * 1024 * 1024  # 4 MB


@dataclass(frozen=True)
class ConfigSnapshotCreateResult:
    snapshot: DeviceConfigSnapshot
    previous_snapshot: DeviceConfigSnapshot | None


@dataclass(frozen=True)
class RollbackEligibility:
    eligible: bool
    blocker: str | None = None


class ConfigSnapshotService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DeviceRepository(session)

    def save_read_result(
        self,
        *,
        device_id: int,
        source_task_id: str,
        datastore: str,
        result: NetconfOperationResult,
        collected_at: datetime | None = None,
    ) -> ConfigSnapshotCreateResult:
        if not result.ok or result.content_digest is None:
            raise ValueError("Only successful config read results can be saved")
        collected = collected_at or datetime.now(UTC)
        previous = self.repository.get_last_config_snapshot(
            device_id=device_id, datastore=datastore
        )
        diff_summary = build_diff_summary(previous, result.content_digest, collected)
        summary = build_snapshot_summary(
            datastore=datastore,
            content_digest=result.content_digest,
            collected_at=collected,
            read_summary=result.summary,
            diff_summary=diff_summary,
        )
        normalized = result.normalized_content
        if normalized and len(normalized.encode("utf-8")) > ROLLBACK_NORMALIZED_CONTENT_MAX_BYTES:
            normalized = None
        snapshot = self.repository.create_config_snapshot(
            device_id=device_id,
            source_task_id=source_task_id,
            datastore=datastore,
            content_digest=result.content_digest,
            collected_at=collected,
            diff_summary=diff_summary,
            summary=summary,
            normalized_content=normalized,
        )
        return ConfigSnapshotCreateResult(snapshot=snapshot, previous_snapshot=previous)

    def assess_rollback_eligibility(self, snapshot: DeviceConfigSnapshot) -> RollbackEligibility:
        if not snapshot.normalized_content:
            return RollbackEligibility(eligible=False, blocker="ROLLBACK_TARGET_NOT_RESTORABLE")
        if not self.repository.is_successful_snapshot_source(snapshot):
            return RollbackEligibility(eligible=False, blocker="ROLLBACK_TARGET_NOT_RESTORABLE")
        return RollbackEligibility(eligible=True)


class RollbackPayloadDeriveError(RuntimeError):
    def __init__(self, message: str, blocker: str) -> None:
        super().__init__(message)
        self.blocker = blocker


@dataclass(frozen=True)
class DerivedRollbackPayload:
    config_body: str
    digest: str
    length: int
    line_count: int
    source_label: str


class RollbackPayloadDeriver:
    def build(
        self, *, target_snapshot: DeviceConfigSnapshot, datastore: str
    ) -> DerivedRollbackPayload:
        if not target_snapshot.normalized_content:
            raise RollbackPayloadDeriveError(
                "Target snapshot does not have restorable normalized content",
                blocker="ROLLBACK_TARGET_NOT_RESTORABLE",
            )
        content = target_snapshot.normalized_content
        if len(content.encode("utf-8")) > ROLLBACK_NORMALIZED_CONTENT_MAX_BYTES:
            raise RollbackPayloadDeriveError(
                "Target snapshot normalized content exceeds size limit",
                blocker="ROLLBACK_TARGET_NOT_RESTORABLE",
            )
        digest = "sha256:" + sha256(content.encode("utf-8")).hexdigest()
        return DerivedRollbackPayload(
            config_body=content,
            digest=digest,
            length=len(content),
            line_count=len(content.splitlines()) if content else 0,
            source_label=f"rollback_from_snapshot:{target_snapshot.id}",
        )


def build_config_object_tree(content: str | None) -> dict[str, object] | None:
    if not content:
        return None
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        return {
            "unparsed_content": {
                "format": "text",
                "line_count": len(lines),
                "content_length": len(content),
            }
        }
    label = _local_name(root.tag)
    tree = {label: _element_to_object(root, parent_namespace=None)}
    return redact_sensitive(tree)  # type: ignore[return-value]


def build_diff_summary(
    previous: DeviceConfigSnapshot | None, current_digest: str, collected_at: datetime
) -> dict[str, object]:
    if previous is None:
        return {
            "changed": False,
            "previous_snapshot_id": None,
            "previous_content_digest": None,
            "current_content_digest": current_digest,
            "digest_changed": False,
            "collected_at_delta_seconds": None,
        }
    changed = previous.content_digest != current_digest
    return {
        "changed": changed,
        "previous_snapshot_id": previous.id,
        "previous_content_digest": previous.content_digest,
        "current_content_digest": current_digest,
        "digest_changed": changed,
        "collected_at_delta_seconds": int(
            (_as_aware(collected_at) - _as_aware(previous.collected_at)).total_seconds()
        ),
    }


def build_snapshot_summary(
    *,
    datastore: str,
    content_digest: str,
    collected_at: datetime,
    read_summary: dict[str, object],
    diff_summary: dict[str, object],
) -> dict[str, object]:
    safe_read_summary = redact_sensitive(read_summary)
    safe_read_summary.pop("config_content", None)
    safe_read_summary.pop("normalized_content", None)
    return {
        "datastore": datastore,
        "content_digest": content_digest,
        "collected_at": collected_at.isoformat(),
        "content_length": safe_read_summary.get("content_length"),
        "normalized_length": safe_read_summary.get("normalized_length"),
        "diff": diff_summary,
    }


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _element_to_object(
    element: ElementTree.Element, *, parent_namespace: str | None
) -> object:
    namespace, _ = _split_tag(element.tag)
    children = list(element)
    attributes = {
        _local_name(key): value
        for key, value in sorted(element.attrib.items(), key=lambda item: _local_name(item[0]))
    }
    text = (element.text or "").strip()

    if not children and not attributes:
        return REDACTED if _is_sensitive_xml_key(element.tag) else text

    node: dict[str, object] = {}
    if namespace and namespace != parent_namespace:
        node["_namespace"] = namespace
    if attributes:
        node["_attributes"] = redact_sensitive(attributes)  # type: ignore[assignment]
    if text:
        node["_text"] = REDACTED if _is_sensitive_xml_key(element.tag) else text

    for child in children:
        child_label = _local_name(child.tag)
        child_value = _element_to_object(child, parent_namespace=namespace)
        existing = node.get(child_label)
        if existing is None:
            node[child_label] = child_value
        elif isinstance(existing, list):
            existing.append(child_value)
        else:
            node[child_label] = [existing, child_value]
    return node


def _split_tag(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local_name = tag[1:].split("}", 1)
        return namespace, local_name
    return None, tag


def _local_name(tag: str) -> str:
    return _split_tag(tag)[1]


def _is_sensitive_xml_key(tag: str) -> bool:
    key = _local_name(tag).lower().replace("-", "_")
    sensitive_parts = ("password", "secret", "private_key", "passphrase", "credential")
    return any(part in key for part in sensitive_parts)
