"""Fail-closed production deploy runner for the restricted ``luma-deploy`` user.

The SSH forced command passes only a tested 40-character commit SHA. Secrets
remain in the protected Compose environment on the host and are never printed.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Sequence
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
COMPOSE = (
    "docker",
    "compose",
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.prod.yml",
)
RUNTIME_CONTRACT = (
    'set -- $(pidof caddy); test "$#" -ge 1; pid="$1"; '
    'grep -Eq "^Uid:[[:space:]]+1000[[:space:]]+1000[[:space:]]+1000[[:space:]]+1000" "/proc/$pid/status"; '
    'grep -Eq "^NoNewPrivs:[[:space:]]+1" "/proc/$pid/status"'
)


class DeployError(RuntimeError):
    """A deployment contract failed without exposing protected values."""


class Executor:
    def __init__(self, cwd: Path):
        self.cwd = cwd

    def run(
        self,
        command: Sequence[str],
        *,
        capture: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> str:
        completed = subprocess.run(
            list(command),
            cwd=self.cwd,
            env=dict(env) if env is not None else None,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
        )
        return completed.stdout.strip() if capture else ""


def resolve_revision(argv: Sequence[str], environ: Mapping[str, str]) -> str:
    if len(argv) > 1:
        raise DeployError("expected exactly one revision")
    raw = argv[0] if argv else environ.get("SSH_ORIGINAL_COMMAND", "")
    revision = raw.strip()
    if not FULL_SHA.fullmatch(revision):
        raise DeployError("revision must be a lowercase 40-character commit SHA")
    return revision


def validate_smoke_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        parsed.port
    except ValueError as exc:
        raise DeployError("SMOKE_BASE_URL is not a valid HTTPS origin") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise DeployError("SMOKE_BASE_URL must be an HTTPS origin without credentials or a path")
    return value.strip().rstrip("/")


def deployment_commands() -> tuple[tuple[str, ...], ...]:
    return (
        COMPOSE + ("config", "--quiet"),
        COMPOSE + ("build", "--pull"),
        COMPOSE + ("up", "-d", "--remove-orphans", "--wait", "--wait-timeout", "240"),
    )


def runtime_contract_command() -> tuple[str, ...]:
    return COMPOSE + (
        "exec",
        "-T",
        "--user",
        "1000:1000",
        "caddy",
        "sh",
        "-ceu",
        RUNTIME_CONTRACT,
    )


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - deployment is Linux-only
        raise DeployError("production deploy locking requires Linux fcntl") from exc
    try:
        handle = path.open("a", encoding="utf-8")
    except OSError as exc:
        raise DeployError(f"cannot open deploy lock {path}") from exc
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise DeployError("another production deploy is already running") from exc
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def probe(origin: str, path: str) -> None:
    request = Request(origin + path, headers={"Accept": "application/json", "User-Agent": "luma-deploy-smoke/1"})
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise DeployError(f"external {path} returned {response.status}")


def deploy(revision: str, environ: Mapping[str, str]) -> None:
    repo = Path(environ.get("LUMA_REPO_DIR", Path(__file__).resolve().parents[1])).resolve()
    lock_path = Path(environ.get("LUMA_DEPLOY_LOCK", "/var/lock/luma-deploy.lock"))
    origin = validate_smoke_base_url(environ.get("SMOKE_BASE_URL", ""))
    minimum = environ.get("LUMA_MIN_DEPLOY_REVISION", "").strip()
    if not FULL_SHA.fullmatch(minimum):
        raise DeployError("LUMA_MIN_DEPLOY_REVISION must be the runner installation commit SHA")
    if not (repo / ".git").exists() or not (repo / "docker-compose.prod.yml").is_file():
        raise DeployError("LUMA_REPO_DIR is not a Luma checkout")

    executor = Executor(repo)
    previous = "unknown"
    with exclusive_lock(lock_path):
        dirty = executor.run(("git", "status", "--porcelain", "--untracked-files=no"), capture=True)
        if dirty:
            raise DeployError("deployment checkout has tracked local changes")
        previous = executor.run(("git", "rev-parse", "HEAD"), capture=True)
        executor.run(("git", "fetch", "--prune", "origin", "main"))
        executor.run(("git", "cat-file", "-e", f"{revision}^{{commit}}"))
        executor.run(("git", "merge-base", "--is-ancestor", revision, "origin/main"))
        executor.run(("git", "merge-base", "--is-ancestor", minimum, revision))
        executor.run(("git", "cat-file", "-e", f"{revision}:scripts/deploy_production.py"))
        executor.run(("git", "checkout", "--detach", revision))
        if executor.run(("git", "rev-parse", "HEAD"), capture=True) != revision:
            raise DeployError("checkout revision mismatch")

        for command in deployment_commands():
            executor.run(command)
        executor.run(runtime_contract_command())
        probe(origin, "/health")
        probe(origin, "/ready")

        synthetic = "not_configured"
        token = environ.get("SMOKE_ACCESS_TOKEN", "")
        if token:
            smoke_env = dict(environ)
            smoke_env["SMOKE_BASE_URL"] = origin
            executor.run((sys.executable, "scripts/production_smoke.py"), env=smoke_env)
            synthetic = "passed"

        print(
            "LUMA_DEPLOY_EVIDENCE "
            f"revision={revision} previous={previous} caddy_uid=1000 "
            f"no_new_privs=1 health=200 ready=200 synthetic={synthetic}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    revision = "unknown"
    try:
        revision = resolve_revision(args, os.environ)
        deploy(revision, os.environ)
        return 0
    except (DeployError, OSError, subprocess.CalledProcessError) as exc:
        print(f"LUMA_DEPLOY_FAILED revision={revision} reason={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
