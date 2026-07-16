import sys
from contextlib import nullcontext
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import deploy_production as deploy_module  # noqa: E402
from deploy_production import (  # noqa: E402
    DeployError,
    deployment_commands,
    resolve_revision,
    runtime_contract_command,
    validate_smoke_base_url,
)


SHA = "a" * 40


def test_revision_accepts_one_exact_sha_from_cli_or_forced_command():
    assert resolve_revision([SHA], {}) == SHA
    assert resolve_revision([], {"SSH_ORIGINAL_COMMAND": SHA}) == SHA


@pytest.mark.parametrize(
    "value",
    ["", "abc", "A" * 40, f"{SHA} --help", f"{SHA}\nrm -rf /"],
)
def test_revision_rejects_non_sha_commands(value):
    with pytest.raises(DeployError):
        resolve_revision([], {"SSH_ORIGINAL_COMMAND": value})


@pytest.mark.parametrize(
    "value",
    [
        "http://example.test",
        "https://user@example.test",
        "https://example.test/path",
        "https://example.test/?token=x",
        "https://example.test:99999",
        "https://[invalid",
        "example.test",
    ],
)
def test_smoke_origin_rejects_unsafe_or_non_origin_urls(value):
    with pytest.raises(DeployError):
        validate_smoke_base_url(value)


def test_smoke_origin_accepts_https_origin_and_normalizes_slash():
    assert validate_smoke_base_url("https://app.example.test/") == "https://app.example.test"


def test_deploy_sequence_builds_every_compose_service_and_removes_orphans():
    commands = deployment_commands()
    assert commands[0][-2:] == ("config", "--quiet")
    assert commands[1][-2:] == ("build", "--pull")
    assert commands[2][-5:] == ("-d", "--remove-orphans", "--wait", "--wait-timeout", "240")


def test_runtime_contract_checks_real_caddy_process_as_uid_1000():
    command = runtime_contract_command()
    assert command[command.index("exec") + 1 : command.index("caddy")] == ("-T", "--user", "1000:1000")
    script = command[-1]
    assert "pidof caddy" in script
    assert "NoNewPrivs" in script
    assert "1000" in script


def test_workflow_has_opt_in_machine_readable_deploy_evidence_gate():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "LUMA_DEPLOY_EVIDENCE_REQUIRED" in workflow
    assert "^LUMA_DEPLOY_EVIDENCE revision=${GITHUB_SHA}" in workflow
    assert "caddy_uid=1000 no_new_privs=1 health=200 ready=200" in workflow


def test_deploy_wires_checkout_compose_runtime_and_external_evidence(monkeypatch, tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docker-compose.prod.yml").write_text("services: {}\n", encoding="utf-8")
    previous = "b" * 40
    calls = []
    probes = []

    class FakeExecutor:
        def __init__(self, cwd):
            assert cwd == tmp_path

        def run(self, command, *, capture=False, env=None):
            command = tuple(command)
            calls.append((command, env))
            if command[:3] == ("git", "status", "--porcelain"):
                return ""
            if command == ("git", "rev-parse", "HEAD"):
                return previous if sum(item[0] == command for item in calls) == 1 else SHA
            return ""

    monkeypatch.setattr(deploy_module, "Executor", FakeExecutor)
    monkeypatch.setattr(deploy_module, "exclusive_lock", lambda _path: nullcontext())
    monkeypatch.setattr(deploy_module, "probe", lambda origin, path: probes.append((origin, path)))
    environ = {
        "LUMA_REPO_DIR": str(tmp_path),
        "LUMA_DEPLOY_LOCK": str(tmp_path / "deploy.lock"),
        "LUMA_MIN_DEPLOY_REVISION": SHA,
        "SMOKE_BASE_URL": "https://app.example.test",
        "SMOKE_ACCESS_TOKEN": "never-print-this-token",
    }

    deploy_module.deploy(SHA, environ)

    commands = [item[0] for item in calls]
    assert ("git", "merge-base", "--is-ancestor", SHA, SHA) in commands
    assert ("git", "cat-file", "-e", f"{SHA}:scripts/deploy_production.py") in commands
    for command in deployment_commands() + (runtime_contract_command(),):
        assert command in commands
    smoke_call, smoke_env = calls[-1]
    assert smoke_call == (sys.executable, "scripts/production_smoke.py")
    assert "never-print-this-token" not in " ".join(smoke_call)
    assert smoke_env["SMOKE_ACCESS_TOKEN"] == "never-print-this-token"
    assert probes == [
        ("https://app.example.test", "/health"),
        ("https://app.example.test", "/ready"),
    ]
    evidence = capsys.readouterr().out
    assert f"revision={SHA} previous={previous}" in evidence
    assert "synthetic=passed" in evidence
    assert "never-print-this-token" not in evidence


def test_deploy_requires_an_immutable_runner_floor(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docker-compose.prod.yml").write_text("services: {}\n", encoding="utf-8")
    with pytest.raises(DeployError, match="LUMA_MIN_DEPLOY_REVISION"):
        deploy_module.deploy(
            SHA,
            {
                "LUMA_REPO_DIR": str(tmp_path),
                "SMOKE_BASE_URL": "https://app.example.test",
            },
        )
