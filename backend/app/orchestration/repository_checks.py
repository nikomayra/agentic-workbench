import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.repository.operations import validate_repository_root
from app.schemas.schemas import RepositoryTarget


@dataclass(frozen=True)
class TestsOutcome:
    passed: bool
    output: str


def run_tests(trusted_root: Path, target: RepositoryTarget) -> TestsOutcome:
    """Run the configured tests in an integration worktree."""
    root = validate_repository_root(trusted_root)
    test_root = (root / target.test_working_directory).resolve()
    if not test_root.is_relative_to(root) or not test_root.is_dir():
        raise RuntimeError("Test working directory is outside the repository.")

    result = subprocess.run(
        target.test_command,
        cwd=test_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()[
        :20_000
    ]

    return TestsOutcome(passed=result.returncode == 0, output=output)


@dataclass(frozen=True)
class GitDiffOutcome:
    output: str
    changed_paths: tuple[Path, ...] = ()


def git_diff(trusted_root: Path, base_branch: str) -> GitDiffOutcome:
    """Return integration-branch changes relative to its configured base."""
    root = validate_repository_root(trusted_root)
    comparison = f"{base_branch}...HEAD"
    result = subprocess.run(
        ["git", "diff", comparison, "--", "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    paths = subprocess.run(
        ["git", "diff", comparison, "--name-only", "--", "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    if result.returncode != 0 or paths.returncode != 0:
        raise RuntimeError("Bad return code", result.stderr or paths.stderr)

    affected_files = tuple(
        Path(line) for line in paths.stdout.splitlines() if line.strip()
    )

    return GitDiffOutcome(
        output=result.stdout if result.stdout else "No changes.",
        changed_paths=affected_files,
    )
