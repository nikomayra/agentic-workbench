import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestsOutcome:
    passed: bool
    output: str


def run_tests(trusted_root: Path) -> TestsOutcome:
    """Run the integration worktree's bounded backend test command."""
    backend_root = trusted_root / "backend"
    if not backend_root.is_dir():
        raise RuntimeError(
            "Unexpected folder structure: no backend folder found. Testing failed."
        )

    result = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=backend_root,
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


def git_diff(trusted_root: Path) -> GitDiffOutcome:
    """Return the integration branch's changes relative to main."""
    result = subprocess.run(
        ["git", "diff", "main...HEAD", "--", "."],
        cwd=trusted_root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError("Bad return code", result.stderr)

    return GitDiffOutcome(output=result.stdout if result.stdout else "No changes.")
