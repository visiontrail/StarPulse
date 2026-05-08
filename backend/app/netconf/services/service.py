from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import StringIO
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from app.common.redaction import redact_sensitive
from app.devices.constants import SUPPORTED_CONFIG_DATASTORES, DeviceAccessErrorCode
from app.netconf.adapters import NcclientNetconfClient
from app.netconf.client import NetconfClient, NetconfConnectionParams
from app.netconf.services.config_digest import config_digest, normalize_config_content
from app.netconf.services.errors import NetconfError


@dataclass(frozen=True)
class NetconfOperationResult:
    ok: bool
    summary: dict[str, object] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    system_info: dict[str, object] = field(default_factory=dict)
    config_content: str | None = None
    datastore: str | None = None
    content_digest: str | None = None
    normalized_content: str | None = None
    error_code: DeviceAccessErrorCode | None = None
    error_message: str | None = None
    context: dict[str, object] = field(default_factory=dict)


class NetconfService:
    def __init__(self, client: NetconfClient | None = None) -> None:
        self.client = client or NcclientNetconfClient()

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return self.client.validate_connection(params)

    def list_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return self.client.get_capabilities(params)

    def test_connection(self, params: NetconfConnectionParams) -> NetconfOperationResult:
        try:
            self.client.validate_connection(params)
        except NetconfError as exc:
            return _error_result(exc)
        return NetconfOperationResult(ok=True, summary={"connected": True})

    def discover_capabilities(self, params: NetconfConnectionParams) -> NetconfOperationResult:
        try:
            capabilities = self.client.get_capabilities(params)
            system_info = self.client.get_system_info(params)
        except NetconfError as exc:
            return _error_result(exc)
        summary = {
            "capability_count": len(capabilities),
            "has_system_info": bool(system_info),
        }
        yang_models = _discover_yang_models_from_capabilities(self.client, params, capabilities)
        if yang_models:
            summary["yang_models"] = yang_models
        return NetconfOperationResult(
            ok=True,
            summary=summary,
            capabilities=capabilities,
            system_info=system_info,
        )

    def read_config(
        self, params: NetconfConnectionParams, datastore: str
    ) -> NetconfOperationResult:
        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            return NetconfOperationResult(
                ok=False,
                error_code=DeviceAccessErrorCode.INVALID_PARAMETER,
                error_message="Unsupported datastore",
                context={
                    "datastore": datastore,
                    "supported_datastores": SUPPORTED_CONFIG_DATASTORES,
                },
            )
        try:
            config_content = self.client.get_config(params, datastore)
        except NetconfError as exc:
            return _error_result(exc)
        normalized_content = normalize_config_content(config_content)
        digest = config_digest(config_content)
        summary = {
            "datastore": datastore,
            "content_digest": digest,
            "content_length": len(config_content),
            "normalized_length": len(normalized_content),
        }
        yang_models = _discover_yang_models_for_config(self.client, params, config_content)
        if yang_models:
            summary["yang_models"] = yang_models
        return NetconfOperationResult(
            ok=True,
            summary=summary,
            config_content=config_content,
            datastore=datastore,
            content_digest=digest,
            normalized_content=normalized_content,
        )


    def write_config(
        self, params: NetconfConnectionParams, datastore: str, config_body: str
    ) -> NetconfOperationResult:
        """Execute an authorized NETCONF edit-config. Only called from change control service."""
        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            return NetconfOperationResult(
                ok=False,
                error_code=DeviceAccessErrorCode.INVALID_PARAMETER,
                error_message="Unsupported datastore",
                context={"datastore": datastore},
            )
        try:
            self.client.edit_config(params, datastore, config_body)
        except NetconfError as exc:
            return _error_result(exc)
        return NetconfOperationResult(
            ok=True,
            summary={"datastore": datastore, "write": "success"},
        )


def _error_result(exc: NetconfError) -> NetconfOperationResult:
    return NetconfOperationResult(
        ok=False,
        error_code=exc.code,
        error_message=exc.safe_message,
        context=redact_sensitive(exc.context),
    )


def _discover_yang_models_from_capabilities(
    client: NetconfClient,
    params: NetconfConnectionParams,
    capabilities: list[str],
) -> list[dict[str, object]]:
    schema_getter = getattr(client, "get_schema", None)
    if not callable(schema_getter):
        return []
    models: list[dict[str, object]] = []
    seen: set[str] = set()
    for module in _modules_from_capabilities(capabilities):
        _append_yang_model_with_imports(schema_getter, params, module, models, seen)
    return models


def _discover_yang_models_for_config(
    client: NetconfClient,
    params: NetconfConnectionParams,
    config_content: str,
) -> list[dict[str, object]]:
    schema_getter = getattr(client, "get_schema", None)
    if not callable(schema_getter):
        return []
    models: list[dict[str, object]] = []
    seen: set[str] = set()
    for namespace in _namespaces_from_xml(config_content):
        for module_name in _module_names_from_namespace(namespace):
            if module_name in seen:
                continue
            loaded = _append_yang_model_with_imports(
                schema_getter,
                params,
                {"module": module_name, "namespace": namespace},
                models,
                seen,
            )
            if loaded:
                break
    return models


def _append_yang_model_with_imports(
    schema_getter: object,
    params: NetconfConnectionParams,
    module: dict[str, str | None],
    models: list[dict[str, object]],
    seen: set[str],
    *,
    depth: int = 0,
) -> bool:
    module_name = module.get("module")
    if not module_name or module_name in seen or len(models) >= 80:
        return False
    seen.add(module_name)
    model = _load_yang_model(schema_getter, params, module)
    if model is None:
        return False
    models.append(model)
    if depth >= 3:
        return True
    imports = model.get("imports")
    if isinstance(imports, list):
        for imported in imports:
            if isinstance(imported, dict):
                _append_yang_model_with_imports(
                    schema_getter,
                    params,
                    {
                        "module": str(imported.get("module") or ""),
                        "revision": (
                            str(imported["revision"]) if imported.get("revision") else None
                        ),
                        "namespace": None,
                    },
                    models,
                    seen,
                    depth=depth + 1,
                )
    return True


def _load_yang_model(
    schema_getter: object,
    params: NetconfConnectionParams,
    module: dict[str, str | None],
) -> dict[str, object] | None:
    module_name = module.get("module")
    if not module_name:
        return None
    try:
        source = schema_getter(params, module_name, module.get("revision"))
    except Exception:
        return None
    parsed = parse_yang_nodes(source)
    if not parsed:
        return None
    namespace = parsed["namespace"] or module.get("namespace")
    model = {
        "module": parsed["module"] or module_name,
        "namespace": namespace,
        "revision": parsed["revision"] or module.get("revision"),
        "node_count": len(parsed["nodes"]),
        "nodes": parsed["nodes"],
        "imports": parsed.get("imports", []),
    }
    return redact_sensitive(model)  # type: ignore[return-value]


def _modules_from_capabilities(capabilities: list[str]) -> list[dict[str, str | None]]:
    modules: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for capability in capabilities:
        if "module=" not in capability:
            continue
        parsed = urlparse(capability)
        query = parse_qs(parsed.query)
        module = query.get("module", [None])[0]
        if not module or module in seen:
            continue
        seen.add(module)
        modules.append(
            {
                "module": module,
                "revision": query.get("revision", [None])[0],
                "namespace": capability.split("?", 1)[0],
            }
        )
    return modules[:80]


def _namespaces_from_xml(content: str) -> list[str]:
    namespaces: list[str] = []
    seen: set[str] = set()
    try:
        iterator = ElementTree.iterparse(StringIO(content), events=("start-ns",))
        for _, (_, namespace) in iterator:
            if namespace not in seen:
                seen.add(namespace)
                namespaces.append(namespace)
    except ElementTree.ParseError:
        for namespace in re.findall(r'xmlns(?::[-\w.]+)?=["\']([^"\']+)["\']', content):
            if namespace not in seen:
                seen.add(namespace)
                namespaces.append(namespace)
    return namespaces


def _module_names_from_namespace(namespace: str) -> list[str]:
    if namespace == "urn:ietf:params:xml:ns:netconf:base:1.0":
        return []
    normalized = namespace.rstrip("/")
    pieces = [part for part in re.split(r"[:/]", normalized) if part]
    candidates: list[str] = []
    if pieces:
        candidates.append(pieces[-1])
    if len(pieces) >= 2:
        candidates.append(f"{pieces[-2]}-{pieces[-1]}")
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def parse_yang_nodes(source: str) -> dict[str, object] | None:
    text = _strip_yang_comments(source)
    module_name = _match(text, r"\bmodule\s+([-\w.]+)\s*\{")
    if not module_name:
        module_name = _match(text, r"\bsubmodule\s+([-\w.]+)\s*\{")
    namespace = _match(text, r"\bnamespace\s+\"([^\"]+)\"\s*;")
    prefix = _match(text, r"\bprefix\s+\"?([-\w.]+)\"?\s*;")
    revision = _match(text, r"\brevision\s+([0-9-]+)\s*\{") or _match(
        text, r"\brevision\s+([0-9-]+)\s*;"
    )
    root_start = text.find("{")
    root_end = _find_matching_brace(text, root_start)
    if root_start < 0 or root_end < 0:
        return None
    nodes: list[dict[str, object]] = []
    _collect_yang_blocks(
        text[root_start + 1 : root_end],
        module=module_name,
        namespace=namespace,
        prefix=prefix,
        parent_path="",
        inherited_config=None,
        nodes=nodes,
    )
    return {
        "module": module_name,
        "namespace": namespace,
        "revision": revision,
        "imports": _parse_imports(text[root_start + 1 : root_end]),
        "nodes": nodes,
    }


def _parse_imports(text: str) -> list[dict[str, str]]:
    imports: list[dict[str, str]] = []
    seen: set[str] = set()
    import_pattern = re.compile(r"\bimport\s+([-\w.]+)\s*(\{|;)")
    pos = 0
    while True:
        match = import_pattern.search(text, pos)
        if match is None:
            break
        module = match.group(1)
        body = ""
        if match.group(2) == "{":
            open_index = text.find("{", match.start())
            close_index = _find_matching_brace(text, open_index)
            body = text[open_index + 1 : close_index] if close_index > open_index else ""
            pos = close_index + 1 if close_index > match.start() else match.end()
        else:
            pos = match.end()
        if module in seen:
            continue
        seen.add(module)
        item = {"module": module}
        revision = _match(body, r"\brevision-date\s+([0-9-]+)\s*;")
        if revision:
            item["revision"] = revision
        imports.append(item)
    return imports


def _collect_yang_blocks(
    text: str,
    *,
    module: str | None,
    namespace: str | None,
    prefix: str | None,
    parent_path: str,
    inherited_config: bool | None,
    nodes: list[dict[str, object]],
) -> None:
    node_pattern = re.compile(r"\b(container|list|leaf|leaf-list)\s+([-\w:.]+)\s*(\{|;)")
    pos = 0
    while True:
        match = node_pattern.search(text, pos)
        if match is None:
            break
        kind, raw_name, opener = match.groups()
        name = _local_yang_name(raw_name)
        open_index = text.find("{", match.start())
        close_index = _find_matching_brace(text, open_index) if opener == "{" else -1
        body = text[open_index + 1 : close_index] if close_index > open_index else ""
        path = f"{parent_path}/{name}" if parent_path else f"/{name}"
        direct = _direct_body_text(body)
        config = _parse_bool_statement(direct, "config")
        if config is None:
            config = inherited_config
        node = {
            "name": name,
            "path": path,
            "module": module,
            "namespace": namespace,
            "prefix": prefix,
            "kind": kind,
            "node_type": kind,
            "type": _parse_type(body) if kind in {"leaf", "leaf-list"} else None,
            "enum_values": _parse_enums(body) if kind in {"leaf", "leaf-list"} else [],
            "range": _parse_type_arg(body, "range") if kind in {"leaf", "leaf-list"} else None,
            "length": _parse_type_arg(body, "length") if kind in {"leaf", "leaf-list"} else None,
            "pattern": _parse_type_arg(body, "pattern") if kind in {"leaf", "leaf-list"} else None,
            "units": (
                _match(body, r"\bunits\s+\"?([^\"';]+)\"?\s*;")
                if kind in {"leaf", "leaf-list"}
                else None
            ),
            "default": (
                _match(body, r"\bdefault\s+\"?([^\"';]+)\"?\s*;")
                if kind in {"leaf", "leaf-list"}
                else None
            ),
            "mandatory": (
                _parse_bool_statement(direct, "mandatory") if kind in {"leaf", "leaf-list"} else None
            ),
            "config": config,
            "status": _match(body, r"\bstatus\s+([-\w]+)\s*;"),
            "description": _match(body, r"\bdescription\s+\"([^\"]*)\"\s*;"),
            "key": _parse_key_statement(body) if kind == "list" else [],
        }
        nodes.append({key: value for key, value in node.items() if value not in (None, [], "")})
        if body:
            _collect_yang_blocks(
                body,
                module=module,
                namespace=namespace,
                prefix=prefix,
                parent_path=path,
                inherited_config=config,
                nodes=nodes,
            )
        pos = close_index + 1 if close_index > match.start() else match.end()


def _parse_type(body: str) -> str | None:
    match = re.search(r"\btype\s+([-\w:.]+)\s*(\{|;)", body)
    return _local_yang_name(match.group(1)) if match else None


def _parse_key_statement(body: str) -> list[str]:
    raw = _match(body, r"\bkey\s+\"([^\"]+)\"\s*;")
    if not raw:
        return []
    return list(dict.fromkeys(_local_yang_name(part) for part in raw.split() if part.strip()))


def _parse_enums(body: str) -> list[dict[str, object]]:
    match = re.search(r"\btype\s+enumeration\s*\{", body)
    if not match:
        return []
    open_index = body.find("{", match.start())
    close_index = _find_matching_brace(body, open_index)
    if close_index <= open_index:
        return []
    type_body = body[open_index + 1 : close_index]
    values: list[dict[str, object]] = []
    enum_pattern = re.compile(r"\benum\s+([-\w:.]+)\s*(\{|;)")
    pos = 0
    while True:
        enum_match = enum_pattern.search(type_body, pos)
        if enum_match is None:
            break
        name = _local_yang_name(enum_match.group(1))
        block_start = type_body.find("{", enum_match.start())
        block_end = (
            _find_matching_brace(type_body, block_start)
            if enum_match.group(2) == "{"
            else -1
        )
        enum_body = type_body[block_start + 1 : block_end] if block_end > block_start else ""
        option = {
            "name": name,
            "value": _match(enum_body, r"\bvalue\s+(-?\d+)\s*;"),
            "description": _match(enum_body, r"\bdescription\s+\"([^\"]*)\"\s*;"),
        }
        values.append({key: value for key, value in option.items() if value not in (None, "")})
        pos = block_end + 1 if block_end > enum_match.start() else enum_match.end()
    return values


def _parse_type_arg(body: str, argument: str) -> str | None:
    return _match(body, rf"\b{argument}\s+\"?([^;\"']+)\"?\s*;")


def _direct_body_text(body: str) -> str:
    # Strips nested {} blocks so only top-level statements are visible.
    # Prevents a child node's "config false;" from polluting the parent's lookup.
    result: list[str] = []
    depth = 0
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            result.append(ch)
    return "".join(result)


def _parse_bool_statement(body: str, field: str) -> bool | None:
    raw = _match(body, rf"\b{field}\s+(true|false)\s*;")
    if raw is None:
        return None
    return raw == "true"


def _strip_yang_comments(source: str) -> str:
    return re.sub(r"//.*?$", "", re.sub(r"/\*.*?\*/", "", source, flags=re.S), flags=re.M)


def _find_matching_brace(text: str, open_index: int) -> int:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "{":
        return -1
    depth = 0
    quote: str | None = None
    for index in range(open_index, len(text)):
        char = text[index]
        prev = text[index - 1] if index > 0 else ""
        if quote:
            if char == quote and prev != "\\":
                quote = None
            continue
        if char in ("\"", "'"):
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def _local_yang_name(name: str) -> str:
    return name.rsplit(":", 1)[-1]
