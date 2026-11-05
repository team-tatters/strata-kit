"""GitHub — two uses of one API. For every manual link `github-releases:owner/repo` (targets without an identifier):
releases since `since` become release records (version, security mention in the body); the repository's security
advisories become vulnerability records with the vendor score and label and the vulnerable/patched ranges — the
advisory API is the real source for these targets, the release body only a hint (manual note 2026-11-03, finding 2)."""
from __future__ import annotations

from kb.security.sources import day, mentions, record

API = "https://api.github.com/repos/"
SEC_WORDS = ("cve-", "security", "vulnerab", "ghsa-")


def repos_from_links(manual_links: dict) -> dict[str, list[str]]:
    """owner/repo → [target_ref…] for links of the form github-releases:owner/repo or github-advisories:owner/repo."""
    out: dict[str, list[str]] = {}
    for target, notice in (manual_links or {}).items():
        if ":" in str(notice) and str(notice).split(":", 1)[0] in ("github-releases", "github-advisories"):
            out.setdefault(str(notice).split(":", 1)[1], []).append(target)
    return out


def parse_releases(repo: str, doc: list, since_iso: str) -> list[dict]:
    out = []
    for r in doc or []:
        pub = day(r.get("published_at") or r.get("created_at"))
        if not pub or pub < since_iso:
            continue
        body = (r.get("body") or "").lower()
        out.append(record(f"github-releases:{repo}:{r.get('tag_name')}", "release", "os-vendor", "github-releases", title=r.get("name") or r.get("tag_name"),
                          source_url=r.get("html_url"), published=pub, version=r.get("tag_name"), security_mentioned=any(w in body for w in SEC_WORDS),
                          affected=[{"kind": "repo", "identifier": repo}], mentions=mentions(r.get("body")), severity_label="prerelease" if r.get("prerelease") else None))
    return out


def parse_advisories(repo: str, doc: list, since_iso: str | None = None) -> list[dict]:
    out = []
    for a in doc or []:
        pub = day(a.get("published_at"))
        if since_iso and pub and pub < since_iso and day(a.get("updated_at")) and day(a.get("updated_at")) < since_iso:
            continue
        cvss = a.get("cvss") or {}
        affected = [{"kind": "repo", "identifier": repo, "ecosystem": (v.get("package") or {}).get("ecosystem"), "package": (v.get("package") or {}).get("name"),
                     "range_text": v.get("vulnerable_version_range"), "fixed": v.get("patched_versions") or None} for v in a.get("vulnerabilities") or []]
        out.append(record(f"github-advisories:{a.get('ghsa_id')}", "vuln", "ecosystem", "github-advisories", vuln_id=a.get("cve_id") or a.get("ghsa_id"),
                          aliases=[x for x in (a.get("ghsa_id"), a.get("cve_id")) if x], title=a.get("summary"), source_url=a.get("html_url"), published=pub,
                          modified=day(a.get("updated_at")), affected=affected or [{"kind": "repo", "identifier": repo}],
                          scores={"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": float(cvss["score"]) if cvss.get("score") is not None else None},
                          severity_label=a.get("severity")))
    return out


def fetch_releases(cfg: dict, since, ctx) -> list[dict]:
    out = []
    for repo in repos_from_links(ctx.manual_links):
        out += parse_releases(repo, ctx.http.json(f"{API}{repo}/releases", params={"per_page": 30}), since.isoformat())
    return out


def fetch(cfg: dict, since, ctx) -> list[dict]:
    out = []
    for repo in repos_from_links(ctx.manual_links):
        out += parse_advisories(repo, ctx.http.json(f"{API}{repo}/security-advisories", params={"per_page": 30, "sort": "published"}), since.isoformat())
    return out
