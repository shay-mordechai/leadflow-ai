# tests/security/test_sec_012_pdf_path_traversal.py
import os

import pytest

from src.services.media.pdf_maker import PDFMaker


@pytest.fixture
def pdf_maker_instance():
    return PDFMaker()


@pytest.fixture(autouse=True)
def cleanup_pdfs():
    """Fixture to clean up any generated PDFs."""
    yield
    output_dir = "storage/pdfs"
    if os.path.exists(output_dir):
        for f in os.listdir(output_dir):
            if f.endswith(".pdf") and "meeting_summary" in f:
                os.remove(os.path.join(output_dir, f))


def test_pdf_path_traversal_remediation(pdf_maker_instance):
    summary_text = "Test summary for path traversal."

    # Test with a path traversal payload
    malicious_filename = "../../../etc/passwd.pdf"
    output_path = pdf_maker_instance.create_meeting_summary(summary_text, malicious_filename)

    # Verify that the output path does not contain path traversal components
    # and is within the intended directory.
    assert "storage/pdfs" in output_path
    assert not ".." in output_path
    assert not "/" in os.path.basename(output_path)  # Ensure no subdirectories in the filename part

    # Verify that the generated file exists in the storage/pdfs directory
    assert os.path.exists(output_path)
    assert os.path.isfile(output_path)

    # Check that the file is indeed in the 'storage/pdfs' directory and not elsewhere
    absolute_output_dir = os.path.abspath("storage/pdfs")
    absolute_output_path = os.path.abspath(output_path)
    assert absolute_output_path.startswith(absolute_output_dir)

    # Test with another malicious filename including directory separators
    malicious_filename_2 = "foo/bar/baz.pdf"
    output_path_2 = pdf_maker_instance.create_meeting_summary(summary_text, malicious_filename_2)
    assert "storage/pdfs" in output_path_2
    assert not "foo" in output_path_2
    assert not "bar" in output_path_2
    assert not "/" in os.path.basename(output_path_2)
    assert os.path.exists(output_path_2)
    assert os.path.isfile(output_path_2)

    # Test with a benign filename
    benign_filename = "report_q3_2026.pdf"
    output_path_3 = pdf_maker_instance.create_meeting_summary(summary_text, benign_filename)
    assert (
        "storage/pdfs/report_q3_2026.pdf" == output_path_3
    )  # Should retain the original benign name
    assert os.path.exists(output_path_3)
    assert os.path.isfile(output_path_3)
