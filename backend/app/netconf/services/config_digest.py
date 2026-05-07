from __future__ import annotations

from hashlib import sha256
from xml.etree import ElementTree


def normalize_config_content(content: str) -> str:
    text = content.strip()
    if not text:
        return ""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
    _strip_whitespace(root)
    return ElementTree.tostring(root, encoding="unicode")


def config_digest(content: str) -> str:
    normalized = normalize_config_content(content)
    return f"sha256:{sha256(normalized.encode('utf-8')).hexdigest()}"


def _strip_whitespace(element: ElementTree.Element) -> None:
    element.text = (element.text or "").strip() or None
    element.tail = (element.tail or "").strip() or None
    for child in element:
        _strip_whitespace(child)
