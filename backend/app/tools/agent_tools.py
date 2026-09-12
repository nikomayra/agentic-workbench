from pathlib import Path

from agents import FunctionTool, function_tool

from app.repository.operations import (
    git_diff,
    list_files,
    read_file,
    run_tests,
    search_code,
    validate_repository_root,
    workspace_info,
)


def make_list_files_tool(trusted_root: Path) -> FunctionTool:
    """Create a list-files tool bound to one application-chosen root."""
    root = validate_repository_root(trusted_root)

    @function_tool(name_override="list_files")
    def scoped_list_files() -> list[str]:
        """Provide relative paths for files in the assigned repository workspace."""
        return list_files(root)

    return scoped_list_files


def make_workspace_info_tool(trusted_root: Path) -> FunctionTool:
    """Create a workspace-info tool bound to one application-chosen root."""
    root = validate_repository_root(trusted_root)

    @function_tool(name_override="workspace_info")
    def scoped_workspace_info() -> dict[str, str]:
        """Provide the assigned repository root and checked-out Git branch."""
        return workspace_info(root)

    return scoped_workspace_info


def make_read_file_tool(trusted_root: Path) -> FunctionTool:
    """Create a read-file tool bound to one application-chosen root."""
    root = validate_repository_root(trusted_root)

    @function_tool(name_override="read_file")
    def scoped_read_file(relative_path: str) -> str:
        """Read one UTF-8 text file from the assigned repository workspace."""
        return read_file(relative_path, root)

    return scoped_read_file


def make_search_code_tool(trusted_root: Path) -> FunctionTool:
    """Create a search-code tool bound to one application-chosen root."""
    root = validate_repository_root(trusted_root)

    @function_tool(name_override="search_code")
    def scoped_search_code(query: str) -> str:
        """Find exact text and return relative paths, line numbers, and matches."""
        return search_code(query, root)

    return scoped_search_code


def make_git_diff_tool(trusted_root: Path) -> FunctionTool:
    """Create a git-diff tool bound to one application-chosen root."""
    root = validate_repository_root(trusted_root)

    @function_tool(name_override="git_diff")
    def scoped_git_diff() -> str:
        """Provide uncommitted repository changes in raw Git diff format."""
        return git_diff(root)

    return scoped_git_diff


def make_run_tests_tool(trusted_root: Path) -> FunctionTool:
    """Create a run-tests tool bound to one application-chosen root."""
    root = validate_repository_root(trusted_root)

    @function_tool(name_override="run_tests")
    def scoped_run_tests() -> str:
        """Run the bounded backend test command and return its exit code and output."""
        return run_tests(root)

    return scoped_run_tests
