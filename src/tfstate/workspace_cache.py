import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

SIDECAR_NAME = ".tfstate-backend.json"


def cache_root() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "tfstate" / "workspaces"


def normalize_s3_uri(uri: str) -> str:
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = re.sub(r"/+", "/", parsed.path.strip("/"))
    return f"s3://{bucket}/{key}"


def fingerprint_s3(uri: str, region: Optional[str], profile: Optional[str]) -> str:
    material = f"{normalize_s3_uri(uri)}:{region or ''}:{profile or ''}"
    return hashlib.sha256(material.encode()).hexdigest()[:8]


def fingerprint_local(path: str | Path) -> str:
    material = str(Path(path).resolve())
    return hashlib.sha256(material.encode()).hexdigest()[:8]


def cached_workspace_path(fingerprint: str) -> Path:
    return cache_root() / fingerprint


def sidecar_path(workspace: str | Path) -> Path:
    return Path(workspace) / SIDECAR_NAME


def read_sidecar(workspace: str | Path) -> Optional[dict[str, Any]]:
    path = sidecar_path(workspace)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "fingerprint" not in data:
        return None
    return data


def write_sidecar(workspace: str | Path, metadata: dict[str, Any]) -> None:
    path = sidecar_path(workspace)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def s3_sidecar_metadata(
    fingerprint: str,
    uri: str,
    region: Optional[str],
    profile: Optional[str],
) -> dict[str, Any]:
    return {
        "fingerprint": fingerprint,
        "backend": "s3",
        "uri": uri,
        "region": region,
        "profile": profile,
    }


def local_sidecar_metadata(fingerprint: str, path: str | Path) -> dict[str, Any]:
    return {
        "fingerprint": fingerprint,
        "backend": "local",
        "path": str(Path(path).resolve()),
    }
