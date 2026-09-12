from pathlib import Path

import pytest

from app.repository.operations import (
    SAMPLE_REPOSITORY_ROOT,
    list_files,
    read_file,
    search_code,
)


def test_list_files_returns_relative_source_paths():
    files = list_files(SAMPLE_REPOSITORY_ROOT)

    assert "backend/app/main.py" in files
    assert "backend/tests/test_reservations.py" in files
    assert all(not Path(file).is_absolute() for file in files)
    assert all(".pytest_cache" not in file for file in files)


def test_read_file_returns_text_contents():
    contents = read_file("backend/app/main.py", SAMPLE_REPOSITORY_ROOT)

    assert "FastAPI" in contents


def test_read_file_rejects_path_outside_repo():
    with pytest.raises(RuntimeError, match="outside the permitted repository"):
        read_file("../../README.md", SAMPLE_REPOSITORY_ROOT)


def test_read_file_rejects_absolute_path():
    absolute_path = SAMPLE_REPOSITORY_ROOT / "backend" / "app" / "main.py"

    with pytest.raises(RuntimeError, match="relative path"):
        read_file(absolute_path.as_posix(), SAMPLE_REPOSITORY_ROOT)


def test_read_file_rejects_binary_file(pdf_file_at_sample_repo_root: Path):
    relative_path = pdf_file_at_sample_repo_root.relative_to(
        SAMPLE_REPOSITORY_ROOT
    ).as_posix()

    with pytest.raises(RuntimeError, match="Unsupported file."):
        read_file(relative_path, SAMPLE_REPOSITORY_ROOT)


def test_read_file_rejects_ignored_file():
    with pytest.raises(RuntimeError, match="Protected or ignored file."):
        read_file("backend/.pytest_cache/README.md", SAMPLE_REPOSITORY_ROOT)


def test_read_file_rejects_oversized_file():
    with pytest.raises(RuntimeError, match="Unsupported file."):
        read_file("backend/uv.lock", SAMPLE_REPOSITORY_ROOT)


def test_search_code_treats_option_like_query_as_literal():
    assert search_code("--help", SAMPLE_REPOSITORY_ROOT) == "No matches found."
