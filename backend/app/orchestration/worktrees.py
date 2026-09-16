"""Create and remove the temporary Git worktrees used by workers."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.repository.operations import SAMPLE_REPOSITORY_ROOT

WORKTREE_ROOT = SAMPLE_REPOSITORY_ROOT.parent / ".agent_worktrees"


@dataclass
class Worktree:
    """The application-controlled Git resources assigned to one worker."""

    id: str
    branch: str
    path: Path


def create_worktree(tree_id: str) -> Worktree:
    """Create one isolated checkout from main for a worker."""
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)

    worktree = Worktree(
        id=tree_id,
        branch=f"worker/{tree_id}",
        path=(WORKTREE_ROOT / tree_id).resolve(),
    )
    result = subprocess.run(
        [
            "git",
            "worktree",
            "add",
            "-b",
            worktree.branch,
            str(worktree.path),
            "main",
        ],
        cwd=SAMPLE_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git worktree creation failed: {result.stderr.strip()}")

    return worktree


def remove_worktree_checkout(worktree: Worktree, force: bool = False) -> None:
    """Remove a checkout, optionally discarding changes in disposable worktrees."""
    if force:
        managed_root = WORKTREE_ROOT.resolve()
        resolved_worktree = worktree.path.resolve()
        if not resolved_worktree.is_relative_to(managed_root):
            raise ValueError("Forced cleanup is limited to managed worktrees.")

        clean_result = subprocess.run(
            ["git", "clean", "-ffdx"],
            cwd=resolved_worktree,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if clean_result.returncode != 0:
            raise RuntimeError(
                f"Git worktree clean failed: {clean_result.stderr.strip()}"
            )

    command = ["git", "worktree", "remove"]
    if force:
        command.append("--force")
    command.append(str(worktree.path))

    remove_result = subprocess.run(
        command,
        cwd=SAMPLE_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if remove_result.returncode != 0:
        raise RuntimeError(
            f"Git worktree removal failed: {remove_result.stderr.strip()}"
        )


def delete_generated_branch(worktree: Worktree) -> None:
    """Delete a branch previously created for an application worktree."""
    branch_result = subprocess.run(
        ["git", "branch", "-D", worktree.branch],
        cwd=SAMPLE_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if branch_result.returncode != 0:
        raise RuntimeError(
            f"Git worker branch removal failed: {branch_result.stderr.strip()}"
        )


@dataclass(frozen=True)
class CommitOutcome:
    committed: bool
    commit_hash: str | None = None


def commit_worktree_changes(worktree: Worktree, commit_message: str) -> CommitOutcome:
    add_result = subprocess.run(
        ["git", "add", "--all", "--", "."],
        cwd=worktree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if add_result.returncode != 0:
        raise RuntimeError(f"Git add failed: {add_result.stderr.strip()}")

    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )

    if not status_result.stdout.strip():
        return CommitOutcome(committed=False)

    commit_result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=worktree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if commit_result.returncode != 0:
        raise RuntimeError(f"Git commit failed: {commit_result.stderr.strip()}")

    rev_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )

    return CommitOutcome(committed=True, commit_hash=rev_result.stdout.strip())


@dataclass(frozen=True)
class MergeOutcome:
    conflicts: bool
    conflict_file_paths: tuple[Path, ...] | None = None


def merge_worktree_changes(
    worktree: Worktree, integration_tree: Worktree
) -> MergeOutcome:
    merge_result = subprocess.run(
        ["git", "merge", worktree.branch],
        cwd=integration_tree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    if merge_result.returncode == 0:
        return MergeOutcome(conflicts=False)
    else:
        unmerged_check = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=integration_tree.path,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if unmerged_check.returncode != 0:
            raise RuntimeError(
                f"Git post-merge diff check failed: {unmerged_check.stderr.strip()}"
            )

        # 1. splitlines() handles multi-platform newlines cleanly
        # 2. strip() and filter out empty lines
        # 3. Path(line) without .resolve() keeps it relative to integration_tree.path
        affected_files = tuple(
            Path(line) for line in unmerged_check.stdout.splitlines() if line.strip()
        )

        if affected_files:
            return MergeOutcome(conflicts=True, conflict_file_paths=affected_files)

        # Non-zero returncode on git merge, but no conflict files found -> true git failure
        raise RuntimeError(
            f"Git merge failed with error: {merge_result.stderr.strip()}"
        )


def complete_merge_after_conflict(integration_tree: Worktree) -> None:
    """
    Verifies conflict resolution, stages files, and completes the Git merge.
    Raises RuntimeError on failure or if unresolved conflict markers are detected.
    """

    unmerged_check = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        cwd=integration_tree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if unmerged_check.returncode != 0:
        raise RuntimeError(
            f"Failed to check unmerged files: {unmerged_check.stderr.strip()}"
        )

    unmerged_files = [
        line.strip() for line in unmerged_check.stdout.splitlines() if line.strip()
    ]

    failed_files = []
    for file_str in unmerged_files:
        file_path = integration_tree.path / file_str
        if not file_path.exists():
            continue  # The agent may have resolved it by deleting the file entirely

        content = file_path.read_text(errors="replace")

        # Correctly check for Git merge markers at the start of any line
        has_markers = any(
            line.startswith(("<<<<<<< ", "||||||| ", ">>>>>>> ")) or line == "======="
            for line in content.splitlines()
        )

        if has_markers:
            failed_files.append(file_str)

    if failed_files:
        raise RuntimeError(
            f"Merge completion rejected. Unresolved conflict markers still exist in: "
            f"{', '.join(failed_files)}"
        )

    add_result = subprocess.run(
        ["git", "add", "--all", "--", "."],
        cwd=integration_tree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if add_result.returncode != 0:
        raise RuntimeError(f"Git add failed: {add_result.stderr.strip()}")

    commit_result = subprocess.run(
        ["git", "commit", "--no-edit"],
        cwd=integration_tree.path,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if commit_result.returncode != 0:
        raise RuntimeError(
            f"Git commit failed during conflict resolution: {commit_result.stderr.strip()}"
        )
