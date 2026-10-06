import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.schemas.schemas import RepositoryTarget


@dataclass(frozen=True)
class RepositoryWorkspace:
    """Runtime filesystem locations derived for one durable workflow."""

    run_id: uuid.UUID
    repository_root: Path
    worktree_root: Path
    target: RepositoryTarget


def _workspace_for(
    run_id: uuid.UUID,
    target: RepositoryTarget,
    managed_root: Path,
) -> RepositoryWorkspace:
    workflow_root = (managed_root.resolve() / str(run_id)).resolve()
    return RepositoryWorkspace(
        run_id=run_id,
        repository_root=workflow_root / "repository",
        worktree_root=workflow_root / "worktrees",
        target=target,
    )


def _validate_managed_workspace(
    workspace: RepositoryWorkspace,
    managed_root: Path,
) -> None:
    root = managed_root.resolve()
    workflow_root = workspace.repository_root.parent.resolve()
    if workflow_root.parent != root:
        raise ValueError("Workspace is outside the application-managed root.")


def _validate_repository_checkout(workspace: RepositoryWorkspace) -> None:
    if not workspace.repository_root.is_dir():
        raise RuntimeError("Managed repository checkout is unavailable.")

    git_result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=workspace.repository_root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if git_result.returncode != 0 or git_result.stdout.strip() != "true":
        raise RuntimeError("Managed repository checkout is not a Git repository.")

    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=workspace.repository_root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if (
        branch_result.returncode != 0
        or branch_result.stdout.strip() != workspace.target.base_branch
    ):
        raise RuntimeError("Managed repository is not on the configured base branch.")


def prepare_workspace(
    run_id: uuid.UUID,
    target: RepositoryTarget,
    managed_root: Path = settings.managed_workspace_root,
) -> RepositoryWorkspace:
    """Clone or reuse the application-controlled checkout for one workflow."""
    root = managed_root.resolve()
    workspace = _workspace_for(run_id, target, root)
    workflow_root = workspace.repository_root.parent

    if workflow_root.exists():
        _validate_managed_workspace(workspace, root)
        _validate_repository_checkout(workspace)
        workspace.worktree_root.mkdir(parents=True, exist_ok=True)
        return workspace

    root.mkdir(parents=True, exist_ok=True)
    workflow_root.mkdir()
    clone_result = subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            target.base_branch,
            "--single-branch",
            target.clone_url,
            str(workspace.repository_root),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if clone_result.returncode != 0:
        shutil.rmtree(workflow_root)
        raise RuntimeError(f"Git clone failed: {clone_result.stderr.strip()}")

    workspace.worktree_root.mkdir()
    _validate_repository_checkout(workspace)
    return workspace


def load_workspace(
    run_id: uuid.UUID,
    target: RepositoryTarget,
    managed_root: Path = settings.managed_workspace_root,
) -> RepositoryWorkspace:
    """Load the expected workspace, creating it when it does not yet exist."""
    return prepare_workspace(run_id, target, managed_root)


def remove_workspace(
    workspace: RepositoryWorkspace,
    managed_root: Path = settings.managed_workspace_root,
) -> None:
    """Remove one workflow workspace only after proving application ownership."""
    _validate_managed_workspace(workspace, managed_root)
    workflow_root = workspace.repository_root.parent
    if workflow_root.exists():
        shutil.rmtree(workflow_root)
