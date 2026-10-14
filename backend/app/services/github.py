import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.repository.workspaces import RepositoryWorkspace

GITHUB_API_URL = "https://api.github.com"
ISSUE_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repository>[A-Za-z0-9_.-]+)/issues/(?P<number>[1-9][0-9]*)/?$"
)


class GitHubIntegrationError(Exception):
    """A GitHub issue could not be loaded or published."""


@dataclass(frozen=True)
class GitHubIssueReference:
    owner: str
    repository: str
    number: int


@dataclass(frozen=True)
class GitHubIssueContext:
    issue_url: str
    objective: str
    clone_url: str
    default_branch: str


def parse_issue_url(issue_url: str) -> GitHubIssueReference:
    match = ISSUE_URL_PATTERN.fullmatch(issue_url.strip())
    if match is None:
        raise GitHubIntegrationError(
            "Issue URL must look like https://github.com/owner/repository/issues/123."
        )
    return GitHubIssueReference(
        owner=match.group("owner"),
        repository=match.group("repository"),
        number=int(match.group("number")),
    )


def load_issue_context(issue_url: str, token: str = "") -> GitHubIssueContext:
    """Load one issue plus the repository information needed by a workflow."""
    reference = parse_issue_url(issue_url)
    repository_path = f"/repos/{reference.owner}/{reference.repository}"
    issue = _request_json(
        "GET",
        f"{repository_path}/issues/{reference.number}",
        token=token,
    )
    repository = _request_json("GET", repository_path, token=token)

    if "pull_request" in issue:
        raise GitHubIntegrationError("The supplied URL points to a pull request.")

    title = _required_string(issue, "title")
    body = issue.get("body")
    objective = title if not isinstance(body, str) or not body.strip() else f"{title}\n\n{body}"

    return GitHubIssueContext(
        issue_url=(
            f"https://github.com/{reference.owner}/{reference.repository}/issues/"
            f"{reference.number}"
        ),
        objective=objective,
        clone_url=_required_string(repository, "clone_url"),
        default_branch=_required_string(repository, "default_branch"),
    )


def publish_draft_pull_request(
    workspace: RepositoryWorkspace,
    result_branch: str,
    issue_url: str,
    objective: str,
    token: str,
) -> str:
    """Push the approved result branch and create one linked draft PR."""
    if not token:
        raise GitHubIntegrationError("GITHUB_TOKEN is required to publish results.")

    reference = parse_issue_url(issue_url)
    expected_repository_url = (
        f"https://github.com/{reference.owner}/{reference.repository}"
    ).lower()
    actual_repository_url = (
        workspace.target.clone_url.rstrip("/").removesuffix(".git").lower()
    )
    if actual_repository_url != expected_repository_url:
        raise GitHubIntegrationError(
            "Workflow repository does not match the configured GitHub issue."
        )

    _push_branch(workspace.repository_root, result_branch, token)
    pull_request = _request_json(
        "POST",
        f"/repos/{reference.owner}/{reference.repository}/pulls",
        token=token,
        payload={
            "title": objective.splitlines()[0][:120],
            "head": result_branch,
            "base": workspace.target.base_branch,
            "body": (
                "Created by Agentic Workbench after human approval.\n\n"
                f"Closes #{reference.number}"
            ),
            "draft": True,
        },
    )
    return _required_string(pull_request, "html_url")


def _push_branch(repository_root: Path, branch: str, token: str) -> None:
    credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {credentials}",
        }
    )
    result = subprocess.run(
        ["git", "push", "origin", f"{branch}:refs/heads/{branch}"],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise GitHubIntegrationError(f"Git push failed: {result.stderr.strip()}")


def _request_json(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "agentic-workbench",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        f"{GITHUB_API_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            result: object = json.loads(response.read())
    except HTTPError as exc:
        raise GitHubIntegrationError(f"GitHub returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubIntegrationError("GitHub request failed.") from exc

    if not isinstance(result, dict):
        raise GitHubIntegrationError("GitHub returned an unexpected response.")
    return result


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise GitHubIntegrationError(f"GitHub response is missing {key}.")
    return value
