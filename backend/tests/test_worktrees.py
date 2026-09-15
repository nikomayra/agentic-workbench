import subprocess
from pathlib import Path

import pytest

import app.orchestration.worktrees as worktrees_module
from app.orchestration.worktrees import (
    Worktree,
    complete_merge_after_conflict,
    merge_worktree_changes,
)
from tests.factories import worktree


def _command_result(
    returncode: int,
    *,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_merge_worktree_changes_returns_success(monkeypatch):
    monkeypatch.setattr(
        worktrees_module.subprocess,
        "run",
        lambda *_args, **_kwargs: _command_result(returncode=0),
    )

    outcome = merge_worktree_changes(
        worktree("backend"),
        worktree("integration"),
    )

    assert outcome.conflicts is False
    assert outcome.conflict_file_paths is None


def test_merge_worktree_changes_returns_conflict_paths(monkeypatch):
    command_results = iter(
        [
            _command_result(returncode=1, stderr="CONFLICT"),
            _command_result(
                returncode=0,
                stdout="backend/app/api.py\nfrontend/src/App.tsx\n",
            ),
        ]
    )
    monkeypatch.setattr(
        worktrees_module.subprocess,
        "run",
        lambda *_args, **_kwargs: next(command_results),
    )

    outcome = merge_worktree_changes(
        worktree("backend"),
        worktree("integration"),
    )

    assert outcome.conflicts is True
    assert outcome.conflict_file_paths == (
        Path("backend/app/api.py"),
        Path("frontend/src/App.tsx"),
    )


def test_merge_worktree_changes_raises_for_non_conflict_failure(monkeypatch):
    command_results = iter(
        [
            _command_result(returncode=1, stderr="fatal: invalid merge"),
            _command_result(returncode=0, stdout=""),
        ]
    )
    monkeypatch.setattr(
        worktrees_module.subprocess,
        "run",
        lambda *_args, **_kwargs: next(command_results),
    )

    with pytest.raises(RuntimeError, match="fatal: invalid merge"):
        merge_worktree_changes(
            worktree("backend"),
            worktree("integration"),
        )


def test_complete_merge_rejects_remaining_conflict_markers(monkeypatch, tmp_path):
    conflicted_file = tmp_path / "app.py"
    conflicted_file.write_text(
        "<<<<<<< ours\nvalue = 1\n=======\nvalue = 2\n>>>>>>> theirs\n"
    )
    monkeypatch.setattr(
        worktrees_module.subprocess,
        "run",
        lambda *_args, **_kwargs: _command_result(
            returncode=0,
            stdout="app.py\n",
        ),
    )

    with pytest.raises(RuntimeError, match="Unresolved conflict markers"):
        complete_merge_after_conflict(
            Worktree(
                id="integration",
                branch="worker/integration",
                path=tmp_path,
            )
        )
