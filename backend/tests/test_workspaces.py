import uuid
from pathlib import Path

import pytest

from app.repository.workspaces import (
    RepositoryWorkspace,
    prepare_workspace,
    remove_workspace,
)
from app.schemas.schemas import RepositoryTarget
from tests.factories import SAMPLE_REPOSITORY_ROOT


def _sample_target() -> RepositoryTarget:
    return RepositoryTarget(
        clone_url=str(SAMPLE_REPOSITORY_ROOT),
        base_branch="main",
        test_command=["uv", "run", "pytest", "-q"],
        test_working_directory="backend",
    )


def test_prepare_workspace_is_idempotent(tmp_path: Path):
    """A retried task reuses its checkout instead of cloning over active work."""
    managed_root = tmp_path / "managed-workspaces"
    run_id = uuid.uuid4()

    first = prepare_workspace(run_id, _sample_target(), managed_root)
    second = prepare_workspace(run_id, _sample_target(), managed_root)

    assert second == first
    assert first.repository_root.is_dir()
    assert (first.repository_root / ".git").is_dir()
    assert first.worktree_root.is_dir()

    remove_workspace(first, managed_root)

    assert not first.repository_root.parent.exists()


def test_prepare_workspace_rejects_invalid_existing_checkout(tmp_path: Path):
    managed_root = tmp_path / "managed-workspaces"
    run_id = uuid.uuid4()
    invalid_checkout = managed_root / str(run_id) / "repository"
    invalid_checkout.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="not a Git repository"):
        prepare_workspace(run_id, _sample_target(), managed_root)


def test_remove_workspace_rejects_unmanaged_path(tmp_path: Path):
    managed_root = tmp_path / "managed-workspaces"
    outside_root = tmp_path / "outside"
    workspace = RepositoryWorkspace(
        run_id=uuid.uuid4(),
        repository_root=outside_root / "repository",
        worktree_root=outside_root / "worktrees",
        target=_sample_target(),
    )

    with pytest.raises(ValueError, match="outside"):
        remove_workspace(workspace, managed_root)
