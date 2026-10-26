"""Fetch, inspect, rank, and bundle public Agent Skills without executing them.

The marketplace supplies popularity. GitHub supplies exact source bytes. SkillWire
keeps popularity, static warnings, and measured evaluation as separate fields.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE = ROOT / "data" / "public-skills"
EVALUATIONS = ROOT / "evidence" / "controlled-evaluations.json"
MARKETPLACE_URL = "https://www.skills.sh/"
GITHUB_API = "https://api.github.com"
USER_AGENT = "skillwire/0.2 (+local, read-only source fetch)"
PUBLIC_SOURCE_REPOS = ("anthropics/skills", "openai/skills", "vercel-labs/agent-skills")
MAX_RESPONSE = 16 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_FILES_PER_SKILL = 120
TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".jsx", ".sh", ".bash", ".zsh", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".html", ".css", ".rb",
    ".go", ".rs", ".java", ".php", ".ps1",
}


class FetchError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip(".-")
    if not cleaned or cleaned in {".", ".."}:
        raise FetchError(f"unsafe path component: {value!r}")
    return cleaned


def _safe_cache_path(cache: Path) -> Path:
    resolved = cache.expanduser().resolve()
    if cache.is_symlink():
        raise FetchError("cache directory must not be a symlink")
    protected = {Path(resolved.anchor), Path.home().resolve(), ROOT.resolve(), Path.cwd().resolve()}
    protected.update(ROOT.parents)
    if resolved in protected:
        raise FetchError(f"refused broad cache directory: {resolved}")
    try:
        ROOT.resolve().relative_to(resolved)
    except ValueError:
        pass
    else:
        raise FetchError("cache directory must not contain the source repository")
    return resolved


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    """Follow HTTPS redirects only, treat 308 like 307 on Python 3.9 and 3.10, and never carry a token to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlparse(newurl)
        if target.scheme != "https":
            raise FetchError(f"refused non-HTTPS redirect: {newurl}")
        new = super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)
        if new is not None and target.netloc != urllib.parse.urlparse(req.full_url).netloc:
            new.remove_header("Authorization")
        return new

    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302


_OPENER = urllib.request.build_opener(_SafeRedirects)


def _get(url: str, limit: int = MAX_RESPONSE) -> tuple[bytes, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and urllib.parse.urlparse(url).netloc == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        headers=headers,
    )
    try:
        with _OPENER.open(request, timeout=25) as response:
            final = response.geturl()
            if urllib.parse.urlparse(final).scheme != "https":
                raise FetchError(f"refused non-HTTPS redirect: {final}")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > limit:
                raise FetchError(f"response is too large: {url}")
            body = response.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise FetchError(f"fetch failed for {url}: {exc}") from exc
    if len(body) > limit:
        raise FetchError(f"response exceeded {limit} bytes: {url}")
    return body, final


_ROW = re.compile(
    r'<a[^>]+href="/(?P<owner>[^/\"]+)/(?P<repo>[^/\"]+)/(?P<slug>[^/\"]+)"[^>]*>'
    r'.*?<span[^>]*>(?P<rank>\d+)</span>'
    r'.*?<h3[^>]*>(?P<name>[^<]+)</h3>'
    r'.*?<p[^>]*>(?P<source>[^<]+)</p>'
    r'.*?<span class="font-mono text-sm text-foreground">(?P<installs>[^<]+)</span>',
    re.DOTALL,
)


def parse_marketplace(raw: str, limit: int) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for match in _ROW.finditer(raw):
        repo = f"{match['owner']}/{match['repo']}"
        slug = html.unescape(match["slug"])
        key = (repo.lower(), slug.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "rank": int(match["rank"]),
                "name": html.unescape(match["name"]).strip(),
                "slug": slug,
                "repo": repo,
                "installs_display": html.unescape(match["installs"]).strip(),
                "marketplace_url": f"https://www.skills.sh/{repo}/{urllib.parse.quote(slug)}",
            }
        )
        if len(rows) >= limit:
            break
    if not rows:
        raise FetchError("skills.sh returned no recognizable leaderboard rows")
    return rows


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    result: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if re.fullmatch(r"[A-Za-z0-9_-]+", key.strip()):
            result[key.strip().lower()] = value.strip().strip("'\"")
    return result


def _kind(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    groups = [
        ("design", ("design", "frontend", "ui", "ux", "visual", "animation")),
        ("code", ("code", "debug", "test", "architecture", "developer", "browser")),
        ("research", ("research", "paper", "source", "investigat")),
        ("writing", ("write", "writing", "content", "copy", "social")),
        ("security", ("security", "audit", "threat", "secret", "vulnerab")),
        ("workflow", ("workflow", "handoff", "plan", "triage", "product", "manage")),
    ]
    for label, words in groups:
        if any(word in text for word in words):
            return label
    return "other"


RISK_PATTERNS = [
    ("fetch_and_execute", "critical", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh)\b", re.I)),
    ("credential_read", "high", re.compile(r"(?:/|~)\.(?:ssh|aws|gnupg)(?:/|\b)|\b(?:id_rsa|id_ed25519|credentials\.json|keychain)\b", re.I)),
    ("environment_secret", "high", re.compile(r"\b(?:process\.env|os\.environ|getenv\s*\()[^\n]*(?:key|token|secret|password|credential)", re.I)),
    ("network_call", "medium", re.compile(r"\b(?:requests\.(?:get|post|put)|urllib\.request|fetch\s*\(|curl\s+|wget\s+)", re.I)),
    ("remote_execute", "critical", re.compile(r"\b(?:eval|exec)\s*\([^\n]*(?:requests|urlopen|fetch|http)", re.I)),
    ("data_send", "high", re.compile(r"\b(?:requests\.(?:post|put)|sendBeacon)\s*\(|\bfetch\s*\([^\n]*\bbody\s*:", re.I)),
    ("file_delete", "high", re.compile(r"\b(?:shutil\.rmtree|os\.(?:remove|unlink))\s*\(|\brm\s+-[a-z]*[rf]", re.I)),
    ("prompt_injection", "high", re.compile(r"\b(?:ignore (?:all |any )?(?:previous|prior) instructions|do not tell (?:the )?user|reveal (?:the )?system prompt|secretly exfiltrat)", re.I)),
]


def scan_folder(folder: Path) -> list[dict]:
    warnings: list[dict] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            raw = path.read_bytes()
            if len(raw) > MAX_FILE or b"\x00" in raw:
                continue
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for rule, severity, pattern in RISK_PATTERNS:
                if pattern.search(line):
                    warnings.append(
                        {
                            "rule": rule,
                            "severity": ("low" if path.suffix.lower() not in {".sh", ".bash", ".zsh", ".py", ".js", ".ts", ".mjs", ".cjs", ".tsx", ".jsx", ".rb", ".go", ".rs", ".java", ".php", ".ps1"} or line.lstrip().startswith(("#", "//", "/*", "*")) else "high" if severity in {"high", "critical"} else "medium"),
                            "context": ("mention" if path.suffix.lower() not in {".sh", ".bash", ".zsh", ".py", ".js", ".ts", ".mjs", ".cjs", ".tsx", ".jsx", ".rb", ".go", ".rs", ".java", ".php", ".ps1"} or line.lstrip().startswith(("#", "//", "/*", "*")) else "action"),
                            "file": path.relative_to(folder).as_posix(),
                            "line": line_number,
                            "text": line.strip()[:500],
                        }
                    )
    return warnings


def _evaluations() -> dict:
    if not EVALUATIONS.is_file():
        return {"evaluations": []}
    return json.loads(EVALUATIONS.read_text(encoding="utf-8"))


def _evaluation(skill_hash: str, records: dict) -> dict:
    for record in records.get("evaluations", []):
        if record.get("skill_sha256") == skill_hash:
            return record
    return {
        "status": "NOT_YET_EVALUATED",
        "label": "Not yet evaluated",
        "score": None,
        "reason": "Popularity and a static scan are not evidence that this skill helps on a task.",
        "gates": {name: "UNKNOWN" for name in ("installed", "read", "used", "improved")},
    }


def _repo_data(repo: str) -> tuple[dict, list[dict], str]:
    encoded = urllib.parse.quote(repo, safe="/")
    meta_raw, _ = _get(f"{GITHUB_API}/repos/{encoded}")
    meta = json.loads(meta_raw)
    branch = meta.get("default_branch")
    if not branch:
        raise FetchError(f"GitHub did not return a default branch for {repo}")
    tree_raw, _ = _get(
        f"{GITHUB_API}/repos/{encoded}/git/trees/{urllib.parse.quote(branch, safe='')}?recursive=1"
    )
    tree = json.loads(tree_raw)
    if tree.get("truncated"):
        raise FetchError(f"GitHub tree is truncated for {repo}; refusing an incomplete skill")
    if not tree.get("sha"):
        raise FetchError(f"GitHub did not return a tree SHA for {repo}")
    return meta, tree.get("tree", []), tree["sha"]


def _skill_root(tree: list[dict], slug: str) -> str | None:
    exact = []
    for item in tree:
        path = item.get("path", "")
        posix = PurePosixPath(path)
        if item.get("type") == "blob" and posix.name.lower() == "skill.md" and posix.parent.name.lower() == slug.lower():
            exact.append(posix.parent.as_posix())
    return min(exact, key=lambda value: (value.count("/"), len(value))) if exact else None


def _download_skill(repo: str, commit: str, root: str, tree: list[dict], destination: Path) -> tuple[int, str]:
    prefix = root.rstrip("/") + "/"
    blobs = [item for item in tree if item.get("type") == "blob" and item.get("path", "").startswith(prefix)]
    if len(blobs) > MAX_FILES_PER_SKILL:
        raise FetchError(f"{repo}/{root} has more than {MAX_FILES_PER_SKILL} files")
    total = 0
    skill_bytes: bytes | None = None
    for item in blobs:
        size = int(item.get("size") or 0)
        if size > MAX_FILE:
            raise FetchError(f"refused file larger than {MAX_FILE} bytes: {item['path']}")
        relative = PurePosixPath(item["path"]).relative_to(PurePosixPath(root))
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise FetchError(f"unsafe source path: {item['path']}")
        raw_url = f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(item['path'], safe='/')}"
        content, _ = _get(raw_url, MAX_FILE)
        total += len(content)
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if relative.name.lower() == "skill.md":
            skill_bytes = content
    if skill_bytes is None:
        raise FetchError(f"SKILL.md disappeared while fetching {repo}/{root}")
    return total, _sha256(skill_bytes)


def fetch(cache: Path = DEFAULT_CACHE, limit: int = 20, max_repos: int = 8, strict: bool = False) -> dict:
    if limit < 1 or limit > 100:
        raise FetchError("limit must be between 1 and 100")
    cache = _safe_cache_path(cache)
    market_raw, market_final = _get(MARKETPLACE_URL)
    rows = parse_marketplace(market_raw.decode("utf-8"), limit)
    allowed_repos: list[str] = []
    for row in rows:
        if row["repo"] not in allowed_repos and len(allowed_repos) < max_repos:
            allowed_repos.append(row["repo"])
    rows = [row for row in rows if row["repo"] in allowed_repos]
    # Publisher discovery supplements the marketplace. Never invent popularity.
    for repo in PUBLIC_SOURCE_REPOS:
        if repo not in allowed_repos:
            allowed_repos.append(repo)
    cache.parent.mkdir(parents=True, exist_ok=True)
    records = _evaluations()
    with tempfile.TemporaryDirectory(prefix="public-skills-", dir=cache.parent) as temp_name:
        temp = Path(temp_name)
        skills_dir = temp / "skills"
        skills: list[dict] = []
        errors: list[dict] = []
        repos: dict[str, tuple[dict, list[dict], str]] = {}
        for repo in allowed_repos:
            try:
                repos[repo] = _repo_data(repo)
            except (FetchError, json.JSONDecodeError) as exc:
                errors.append({"repo": repo, "error": str(exc)})
        seen = {(row["repo"].lower(), row["slug"].lower()) for row in rows}
        for repo in PUBLIC_SOURCE_REPOS:
            if repo not in repos:
                continue
            roots = sorted({str(PurePosixPath(item["path"]).parent)
                            for item in repos[repo][1] if item.get("type") == "blob"
                            and PurePosixPath(item.get("path", "")).name == "SKILL.md"
                            and not any(part in {".git", ".system"} for part in PurePosixPath(item["path"]).parts)})
            added = 0
            for root in roots:
                slug = PurePosixPath(root).name
                if (repo.lower(), slug.lower()) in seen:
                    continue
                seen.add((repo.lower(), slug.lower()))
                rows.append({"repo": repo, "slug": slug, "name": slug,
                             "source_path": root, "rank": None,
                             "installs_display": "Unknown", "marketplace_url": None})
                added += 1
                if added == 2:
                    break
        for row in rows:
            if row["repo"] not in repos:
                continue
            meta, tree, tree_sha = repos[row["repo"]]
            # The recursive tree is pinned by its root SHA, so a moving branch
            # cannot mix file versions while the selected folder is downloaded.
            root = row.get("source_path") or _skill_root(tree, row["slug"])
            if root is None:
                errors.append({"repo": row["repo"], "skill": row["slug"], "error": "SKILL.md folder not found"})
                continue
            local_id = f"{_safe_part(row['repo'].replace('/', '__'))}--{_safe_part(row['slug'])}"
            destination = skills_dir / local_id
            try:
                byte_count, skill_hash = _download_skill(row["repo"], tree_sha, root, tree, destination)
                skill_text = (destination / "SKILL.md").read_text(encoding="utf-8")
            except (FetchError, OSError, UnicodeDecodeError) as exc:
                errors.append({"repo": row["repo"], "skill": row["slug"], "error": str(exc)})
                continue
            frontmatter = _frontmatter(skill_text)
            description = frontmatter.get("description", "No description in SKILL.md front matter.")
            warnings = scan_folder(destination)
            source_url = f"https://github.com/{row['repo']}/tree/{tree_sha}/{root}"
            skills.append(
                {
                    "id": local_id,
                    "name": frontmatter.get("name") or row["name"],
                    "slug": row["slug"],
                    "description": description,
                    "kind": _kind(row["name"], description),
                    "rank": row["rank"],
                    "installs_display": row["installs_display"],
                    "repo": row["repo"],
                    "repo_stars": meta.get("stargazers_count"),
                    "license": (meta.get("license") or {}).get("spdx_id") or "NOASSERTION",
                    "commit": tree_sha,
                    "source_path": root,
                    "source_url": source_url,
                    "marketplace_url": row["marketplace_url"],
                    "skill_sha256": skill_hash,
                    "bytes": byte_count,
                    "folder": f"skills/{local_id}",
                    "evaluation": _evaluation(skill_hash, records),
                    "warnings": warnings,
                }
            )
        skills.sort(key=lambda item: (item["rank"] is None, item["rank"] or 0, item["id"]))
        catalog = {
            "schema": 1,
            "generated_at": _now(),
            "marketplace_url": market_final,
            "source_policy": "Ranks and installs from skills.sh only. Additional publisher skills have unknown popularity. Source versions pinned to GitHub trees.",
            "skills": skills,
            "evaluations": records.get("evaluations", []),
            "errors": errors,
            "sources": [market_final]
            + [f"https://github.com/{repo}" for repo in allowed_repos],
        }
        fatal_errors = [item for item in errors if item["error"] != "SKILL.md folder not found"]
        if strict and fatal_errors:
            raise FetchError(f"strict fetch refused {len(fatal_errors)} failed source downloads; existing cache was kept")
        (temp / "catalog.json").write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if cache.exists():
            shutil.rmtree(cache)
        os.replace(temp, cache)
    return catalog


def load_catalog(cache: Path = DEFAULT_CACHE) -> dict:
    cache = _safe_cache_path(cache)
    path = cache / "catalog.json"
    if not path.is_file():
        raise FetchError("No public skill cache. Run: python3 public_skill_finder.py fetch")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("schema") != 1 or not isinstance(catalog.get("skills"), list):
        raise FetchError("Public skill cache has an unsupported schema")
    for skill in catalog["skills"]:
        folder = (cache / skill["folder"]).resolve()
        try:
            folder.relative_to(cache.resolve())
        except ValueError as error:
            raise FetchError("cached folder escapes the cache") from error
        if folder.is_dir():
            skill["warnings"] = scan_folder(folder)
    return catalog


def select_skills(catalog: dict, ids: Iterable[str] = (), top: int | None = None, kind: str | None = None, safe_only: bool = False) -> list[dict]:
    wanted = set(ids)
    known = {skill["id"] for skill in catalog["skills"]}
    unknown = wanted - known
    if unknown:
        raise FetchError("Unknown skill id: " + ", ".join(sorted(unknown)))
    selected = [skill for skill in catalog["skills"] if not wanted or skill["id"] in wanted]
    if kind:
        selected = [skill for skill in selected if skill["kind"] == kind]
    if safe_only:
        selected = [skill for skill in selected if not skill.get("warnings")]
    if top is not None:
        if top < 1 or top > 20:
            raise FetchError("top must be between 1 and 20")
        selected = selected[:top]
    if not selected:
        raise FetchError("No skills matched the selection")
    return selected


def bundle_bytes(cache: Path, selected: list[dict]) -> bytes:
    cache = _safe_cache_path(cache)
    catalog = load_catalog(cache)
    by_id = {skill["id"]: skill for skill in catalog["skills"]}
    cache_root = cache.resolve()
    output = io.BytesIO()
    manifest = {"created_at": _now(), "skills": []}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for request in selected:
            skill = by_id.get(request["id"])
            if skill is None:
                raise FetchError(f"skill is no longer in the cache: {request['id']}")
            folder = (cache / skill["folder"]).resolve()
            try:
                folder.relative_to(cache_root)
            except ValueError as exc:
                raise FetchError(f"cached folder escapes the cache: {skill['id']}") from exc
            if not folder.is_dir():
                raise FetchError(f"cached folder is missing: {skill['id']}")
            root_name = _safe_part(skill["slug"])
            for path in sorted(folder.rglob("*")):
                if path.is_symlink():
                    raise FetchError(f"cached skill contains a symlink: {skill['id']}")
                if path.is_file():
                    archive.write(path, f"{root_name}/{path.relative_to(folder).as_posix()}")
            manifest["skills"].append(
                {key: skill[key] for key in ("name", "repo", "commit", "source_url", "skill_sha256", "evaluation", "warnings")}
            )
        archive.writestr("SKILL-SOURCES.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return output.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch popular public skills, scan them, and build a local stack.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch_parser = sub.add_parser("fetch", help="Refresh the local cache from skills.sh and pinned GitHub source")
    fetch_parser.add_argument("--limit", type=int, default=20)
    fetch_parser.add_argument("--max-repos", type=int, default=8)
    fetch_parser.add_argument("--strict", action="store_true", help="Keep the existing cache and fail if any requested source is incomplete")
    list_parser = sub.add_parser("list", help="List cached skills without network access")
    list_parser.add_argument("--kind")
    bundle_parser = sub.add_parser("bundle", help="Write selected cached skill folders to a zip")
    bundle_parser.add_argument("--top", type=int, default=5)
    bundle_parser.add_argument("--kind")
    bundle_parser.add_argument("--include-warned", action="store_true", help="Allow statically warned folders in an automatic top selection")
    bundle_parser.add_argument("--output", type=Path, default=Path("skillwire-skill-stack.zip"))
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            catalog = fetch(args.cache_dir, args.limit, args.max_repos, strict=args.strict)
            risky = sum(bool(skill["warnings"]) for skill in catalog["skills"])
            print(f"Cached {len(catalog['skills'])} skills from {len(catalog['sources']) - 1} GitHub repositories; {risky} have static warnings.")
            if catalog["errors"]:
                print(f"Skipped {len(catalog['errors'])} incomplete source rows. See catalog.json.")
        elif args.command == "list":
            catalog = load_catalog(args.cache_dir)
            for skill in select_skills(catalog, kind=args.kind):
                print(f"{str(skill['rank'] or 'Unranked'):>8}  {skill['kind']:<9} {skill['name']:<32} {skill['evaluation']['label']}")
        else:
            catalog = load_catalog(args.cache_dir)
            chosen = select_skills(catalog, top=args.top, kind=args.kind, safe_only=not args.include_warned)
            args.output.write_bytes(bundle_bytes(args.cache_dir, chosen))
            print(f"Wrote {args.output} with {len(chosen)} skill folders.")
    except (FetchError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0




def display_catalog(cache: Path = DEFAULT_CACHE) -> dict:
    try:
        return load_catalog(cache)
    except (FetchError, OSError, json.JSONDecodeError):
        result = json.loads((ROOT / "evidence" / "leaderboard-snapshot.json").read_text())
        result["snapshot"] = True
        return result


def materialize(cache: Path, selected: list[dict]) -> None:
    """Fetch missing folders at the exact displayed tree, checking their digest."""
    cache = _safe_cache_path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache / "catalog.json").exists():
        (cache / "catalog.json").write_text(json.dumps(display_catalog(cache)))
    for skill in selected:
        destination = (cache / skill["folder"]).resolve()
        destination.relative_to(cache.resolve())
        if (destination / "SKILL.md").is_file():
            continue
        raw, _ = _get(f"{GITHUB_API}/repos/{skill['repo']}/git/trees/{skill['commit']}?recursive=1")
        tree = json.loads(raw)
        if tree.get("truncated") or tree.get("sha") != skill["commit"]:
            raise FetchError("Pinned source tree unavailable; refresh and retry")
        with tempfile.TemporaryDirectory(prefix="skill-", dir=cache) as temp:
            folder = Path(temp) / "folder"
            _, digest = _download_skill(skill["repo"], skill["commit"], skill["source_path"], tree["tree"], folder)
            if digest != skill["skill_sha256"]:
                raise FetchError("Source digest changed; refresh and retry")
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(folder, destination)


if __name__ == "__main__":
    raise SystemExit(main())
