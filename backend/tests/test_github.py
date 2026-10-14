import subprocess
import uuid
from pathlib import Path

import pytest

import app.services.github as github_module
from app.repository.workspaces import RepositoryWorkspace
from app.schemas.schemas import RepositoryTarget
from app.services.github import (
    GitHubIntegrationError,
    load_issue_context,
    parse_issue_url,
    publish_draft_pull_request,
)


def _github_workspace(repository_root: Path) -> RepositoryWorkspace:
    return RepositoryWorkspace(
        run_id=uuid.uuid4(),
        repository_root=repository_root,
        worktree_root=repository_root.parent / "worktrees",
        target=RepositoryTarget(
            clone_url="https://github.com/example/project.git",
            base_branch="main",
            test_command=["pytest"],
        ),
    )


def test_load_issue_context_derives_objective_and_repository(monkeypatch):
    responses = iter(
        [
            {"title": "Validate dates", "body": "Reject invalid ranges."},
            {
                "clone_url": "https://github.com/example/project.git",
                "default_branch": "main",
            },
        ]
    )
    monkeypatch.setattr(
        github_module,
        "_request_json",
        lambda *_args, **_kwargs: next(responses),
    )

    result = load_issue_context(
        "https://github.com/example/project/issues/12",
        token="token",
    )

    assert result.objective == "Validate dates\n\nReject invalid ranges."
    assert result.clone_url == "https://github.com/example/project.git"
    assert result.default_branch == "main"


def test_publish_pushes_result_branch_and_creates_draft_pr(monkeypatch, tmp_path):
    pushed: list[tuple[Path, str, str]] = []
    request_payloads: list[dict[str, object] | None] = []
    monkeypatch.setattr(
        github_module,
        "_push_branch",
        lambda root, branch, token: pushed.append((root, branch, token)),
    )

    def fake_request(_method, _path, *, token, payload=None):
        assert token == "token"
        request_payloads.append(payload)
        return {"html_url": "https://github.com/example/project/pull/44"}

    monkeypatch.setattr(github_module, "_request_json", fake_request)
    workspace = _github_workspace(tmp_path / "repository")

    result = publish_draft_pull_request(
        workspace,
        "worker/integration-1",
        "https://github.com/example/project/issues/12",
        "Validate dates\n\nReject invalid ranges.",
        "token",
    )

    assert result == "https://github.com/example/project/pull/44"
    assert pushed == [(workspace.repository_root, "worker/integration-1", "token")]
    assert request_payloads[0] is not None
    assert request_payloads[0]["draft"] is True
    assert request_payloads[0]["base"] == "main"


def test_push_authentication_keeps_token_out_of_command(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(github_module.subprocess, "run", fake_run)

    github_module._push_branch(tmp_path, "worker/result", "secret-token")

    command = captured["command"]
    assert isinstance(command, list)
    assert "secret-token" not in command
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert environment["GIT_CONFIG_KEY_0"] == "http.extraHeader"


def test_parse_issue_url_rejects_non_github_urls():
    with pytest.raises(GitHubIntegrationError, match="Issue URL"):
        parse_issue_url("https://example.com/project/issues/12")
