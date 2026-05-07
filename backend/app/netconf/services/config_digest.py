from __future__ import annotations

import re
from hashlib import sha256
from xml.etree import ElementTree
from xml.sax.saxutils import escape

_XML_ATTRIBUTE_ESCAPE = {'"': "&quot;"}
_CLARK_NOTATION_TAG_RE = re.compile(
    r"<(/?)\{([^}]+)\}([A-Za-z_][A-Za-z0-9_.:-]*)(?=[\s>/])"
)
_ROOT_START_RE = re.compile(r"<[A-Za-z_][A-Za-z0-9_.:-]*(?=[\s>/])")


def normalize_config_content(content: str) -> str:
    text = content.strip()
    if not text:
        return ""
    try:
        root = parse_config_xml(text)
    except ElementTree.ParseError:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
    _strip_whitespace(root)
    return ElementTree.tostring(root, encoding="unicode")


def config_digest(content: str) -> str:
    normalized = normalize_config_content(content)
    return f"sha256:{sha256(normalized.encode('utf-8')).hexdigest()}"


def parse_config_xml(content: str) -> ElementTree.Element:
    text = content.strip()
    try:
        return ElementTree.fromstring(text)
    except ElementTree.ParseError:
        repaired = _repair_clark_notation_xml(text)
        if repaired is None:
            raise
        return ElementTree.fromstring(repaired)


def _strip_whitespace(element: ElementTree.Element) -> None:
    element.text = (element.text or "").strip() or None
    element.tail = (element.tail or "").strip() or None
    for child in element:
        _strip_whitespace(child)


def _repair_clark_notation_xml(content: str) -> str | None:
    prefix_by_namespace: dict[str, str] = {}

    def replace_tag(match: re.Match[str]) -> str:
        slash, namespace, local_name = match.groups()
        prefix = prefix_by_namespace.setdefault(namespace, f"ns{len(prefix_by_namespace)}")
        return f"<{slash}{prefix}:{local_name}"

    repaired = _CLARK_NOTATION_TAG_RE.sub(replace_tag, content)
    if not prefix_by_namespace:
        return None
    root_match = _ROOT_START_RE.search(repaired)
    if root_match is None:
        return None
    declarations = "".join(
        f' xmlns:{prefix}="{escape(namespace, _XML_ATTRIBUTE_ESCAPE)}"'
        for namespace, prefix in prefix_by_namespace.items()
    )
    insert_at = root_match.end()
    return f"{repaired[:insert_at]}{declarations}{repaired[insert_at:]}"
