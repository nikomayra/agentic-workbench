import subprocess
from pathlib import Path

IGNORED_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    ".env",
}

MAX_FILE_BYTES = 20_000


def _find_sample_repository_root() -> Path:
    current_path = Path(__file__).resolve().parent

    for directory in [current_path] + list(current_path.parents):
        target_path = directory / "fixtures" / "sample_repo"
        if target_path.is_dir():
            return target_path.resolve()

    raise FileNotFoundError(
        "fixtures/sample_repo dir could not be found in parents of this file"
    )


SAMPLE_REPOSITORY_ROOT = _find_sample_repository_root()


def validate_repository_root(trusted_root: Path) -> Path:
    root = trusted_root.resolve()
    if not root.is_dir():
        raise RuntimeError("Repository workspace is unavailable.")
    return root


def list_files(trusted_root: Path) -> list[str]:
    root = validate_repository_root(trusted_root)
    file_paths: list[str] = []

    for path in root.rglob("*"):
        relative_path = path.relative_to(root).as_posix()
        if any(part in IGNORED_NAMES for part in Path(relative_path).parts):
            continue

        if path.is_file() and not path.is_symlink():
            file_paths.append(relative_path)

    return sorted(file_paths)


def workspace_info(trusted_root: Path) -> dict[str, str]:
    root = validate_repository_root(trusted_root)
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if branch_result.returncode != 0:
        raise RuntimeError(f"Git branch lookup failed: {branch_result.stderr}")

    return {
        "root": root.as_posix(),
        "branch": branch_result.stdout.strip(),
    }


def read_file(relative_path: str, trusted_root: Path) -> str:
    root = validate_repository_root(trusted_root)
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise RuntimeError("Path must be a relative path.")

    requested_path = root / candidate
    if requested_path.is_symlink():
        raise RuntimeError("Unsupported file.")

    target_full_path = requested_path.resolve()
    try:
        validated_relative_path = Path(
            target_full_path.relative_to(root).as_posix()
        )
    except ValueError:
        raise RuntimeError("Path is outside the permitted repository.") from None

    if any(part in IGNORED_NAMES for part in validated_relative_path.parts):
        raise RuntimeError("Protected or ignored file.")

    if not target_full_path.is_file():
        raise RuntimeError("File does not exist.")

    if target_full_path.stat().st_size > MAX_FILE_BYTES:
        raise RuntimeError("Unsupported file.")

    file_content = target_full_path.read_bytes()
    if b"\x00" in file_content:
        raise RuntimeError("Unsupported file.")

    try:
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeError("Unsupported file.") from None


def search_code(query: str, trusted_root: Path) -> str:
    root = validate_repository_root(trusted_root)
    query = query.strip()
    if not query:
        raise RuntimeError("Query can not be empty.")

    result = subprocess.run(
        ["rg", "--line-number", "--fixed-strings", "--", query, "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    if result.returncode not in [0, 1]:
        raise RuntimeError("Bad return code", result.stderr)

    if result.returncode == 1:
        return "No matches found."

    result_lines = result.stdout.splitlines()
    limited_lines = result_lines[:100]
    final_output = "\n".join(limited_lines)
    return final_output[:20_000]


def git_status(trusted_root: Path) -> str:
    root = validate_repository_root(trusted_root)
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Git status failed: {result.stderr}")

    return result.stdout if result.stdout else "No changes in sandbox."


def git_diff(trusted_root: Path) -> str:
    root = validate_repository_root(trusted_root)
    result = subprocess.run(
        ["git", "diff", "--relative", "--", "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError("Bad return code", result.stderr)

    return result.stdout if result.stdout else "No changes."


def run_tests(trusted_root: Path) -> str:
    """Run the sample repository's bounded backend test command."""
    root = validate_repository_root(trusted_root)
    backend_root = root / "backend"
    if not backend_root.is_dir():
        raise RuntimeError("Repository does not contain a backend test directory.")

    result = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return f"pytest exit code: {result.returncode}\n{output}"[:20_000]
