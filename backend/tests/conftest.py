import pytest
from agents import set_tracing_disabled

from app.repository.operations import SAMPLE_REPOSITORY_ROOT

set_tracing_disabled(True)


@pytest.fixture
def pdf_file_at_sample_repo_root():
    file_path = SAMPLE_REPOSITORY_ROOT / "sample.pdf"
    fake_pdf_bytes = b"%PDF-1.4\x00 fake pdf content for testing"

    file_path.write_bytes(fake_pdf_bytes)

    yield file_path

    if file_path.exists():
        file_path.unlink()
