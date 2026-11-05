"""Compose generator: every `image:` of a compose file becomes an image item (tag, or digest, or the floating tag
`latest`); the source is the manual link registered for project/environment/service, else none and the item is a
blind candidate (DEC-2026-11-03-03). Images from an internal registry prefix are our own builds: their libraries are
seen by the repository inventories, so they are not blind. The host OS is one item from the registry's os: spec and
the installed packages (a dpkg-query listing) become package items with deb purls — the Ubuntu notices match on them
(manual note 2026-11-03, finding 3)."""
from __future__ import annotations

from pathlib import Path

import yaml

from kb.security.generators import item

OS_SOURCE = {"ubuntu": "ubuntu-usn", "debian": "debian-tracker", "alpine": "alpine-secdb", "macos": "apple-security-releases",
             "windows": "msrc", "amazon linux": "none"}


def split_image(ref: str) -> tuple[str, str, bool]:
    """'repo/name:tag' | 'repo/name@sha256:…' | 'name' → (repo, version, floating)."""
    if "@" in ref:
        repo, digest = ref.split("@", 1)
        return repo, digest, False
    last = ref.rsplit("/", 1)[-1]
    if ":" in last:
        repo, tag = ref.rsplit(":", 1)
        return repo, tag, tag in ("latest", "dev", "dev-latest", "main", "stable", "edge") or tag.endswith("-latest")
    return ref, "latest", True


def os_items(os_spec: dict | None, environment: str) -> list[dict]:
    if not os_spec or not os_spec.get("name"):
        return []
    name = str(os_spec["name"])
    src = OS_SOURCE.get(name.lower(), "none")
    extra = {k: os_spec[k] for k in ("codename", "kernel", "installed_kernel") if os_spec.get(k)}
    out = [item(name, str(os_spec.get("version") or "unknown"), environment, "os", src, "none", blind_candidate=src == "none", **extra)]
    if os_spec.get("kernel") and os_spec.get("installed_kernel") and os_spec["kernel"] != os_spec["installed_kernel"]:
        out[0]["reboot_pending"] = True
    return out


def package_items(path: Path, environment: str, os_spec: dict | None) -> list[dict]:
    """dpkg-query -W -f='${Package} ${Version}\\n' → package items; purl pkg:deb/ubuntu/<name>@<version>?distro=<codename>."""
    distro = (os_spec or {}).get("codename") or "unknown"
    vendor = str((os_spec or {}).get("name", "debian")).lower()
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name, ver = parts[0], parts[1]
        out.append(item(name, ver, environment, "package", OS_SOURCE.get(vendor, "none"), f"pkg:deb/{vendor}/{name}@{ver}?distro={distro}",
                        codename=distro, file=Path(path).name))
    return out


def generate(paths: list[Path], environment: str, project: str, os_spec: dict | None = None, manual_links: dict | None = None,
             internal_prefixes: list[str] | None = None, packages: Path | None = None) -> list[dict]:
    links = manual_links or {}
    prefixes = tuple(internal_prefixes or ())
    out: list[dict] = os_items(os_spec, environment)
    if packages:
        out += package_items(packages, environment, os_spec)
    for p in paths:
        doc = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
        for svc, spec in (doc.get("services") or {}).items():
            ref = (spec or {}).get("image")
            if not ref:
                continue
            repo, version, floating = split_image(str(ref))
            link = links.get(f"{project}/{environment}/{svc}")
            internal = bool(prefixes) and repo.startswith(prefixes)
            extra = {k: spec[k] for k in ("exposed", "note") if isinstance(spec, dict) and spec.get(k)}
            out.append(item(svc, version, environment, "image", link or ("internal-build" if internal else "none"), "none", image=repo, file=Path(p).name,
                            blind_candidate=not link and not internal, floating_tag=floating, **extra))
    return out
