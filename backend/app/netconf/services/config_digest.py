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
    return _normalize_element(root)


def config_digest(content: str) -> str:
    normalized = normalize_config_content(content)
    return f"sha256:{sha256(normalized.encode('utf-8')).hexdigest()}"


def _normalize_element(element: ElementTree.Element) -> str:
    attrs = "".join(f' {key}="{value}"' for key, value in sorted(element.attrib.items()))
    text = (element.text or "").strip()
    children = "".join(_normalize_element(child) for child in list(element))
    tail = (element.tail or "").strip()
    return f"<{element.tag}{attrs}>{text}{children}</{element.tag}>{tail}"
