# src/services/media/pdf_maker.py
import logging
import os
import re
import tempfile

from fpdf import FPDF

logger = logging.getLogger("PDFMaker")


class PDFMaker:
    """
    Service for generating simple PDF reports (Meeting Summaries / Receipts).
    """

    def create_meeting_summary(self, summary_text: str, filename: str) -> str:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Font handling:
        # Standard fonts (Arial) don't support Hebrew properly (requires TTF).
        # For this MVP, we use standard font and handle encoding gracefully.
        pdf.set_font("Arial", size=12)

        pdf.cell(200, 10, txt="Meeting Summary", ln=True, align="C")
        pdf.ln(10)

        # Add text content
        # We encode to latin-1 to prevent crashes on non-ascii characters (Hebrew placeholder)
        # In a production environment, you should load a UTF-8 compatible font (e.g., DejaVuSans).
        safe_text = summary_text.encode("latin-1", "replace").decode("latin-1")

        for line in safe_text.split("\n"):
            pdf.multi_cell(0, 10, txt=line)

        # Ensure storage directory exists
        output_dir = "storage/pdfs"
        os.makedirs(output_dir, exist_ok=True)

        # Sanitize filename to prevent path traversal
        # 1. Strip directory components: basename
        base_filename = os.path.basename(filename)

        # Separate filename and extension
        name_without_ext, _ext = os.path.splitext(base_filename)

        # 2. Allow only safe characters (alphanumeric, underscore, hyphen) in the name part
        sanitized_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name_without_ext)

        # 3. Enforce .pdf extension
        sanitized_filename = f"{sanitized_name}.pdf"
        # Ensure storage directory exists
        output_dir = "storage/pdfs"
        os.makedirs(output_dir, exist_ok=True)
        # Verify the resolved path stays strictly inside the target output directory
        # This is a crucial step to prevent writing outside the intended directory.
        potential_output_path = os.path.join(output_dir, sanitized_filename)
        # Use realpath to resolve any symlinks or relative path components (like ../)
        # Then, check if the resolved path starts with the realpath of the output directory
        # and if the filename itself is not a directory.
        absolute_output_dir = os.path.abspath(output_dir)
        absolute_potential_output_path = os.path.abspath(potential_output_path)

        if not absolute_potential_output_path.startswith(absolute_output_dir + os.sep) and not (
            absolute_potential_output_path == absolute_output_dir and sanitized_filename != ""
        ):
            # If path traversal is detected or filename is a directory-like entry,
            # revert to a safe default or raise an error.
            logger.warning(
                f"Path traversal attempt detected with filename: {filename}. Using a safe default."
            )
            sanitized_filename = (
                f"meeting_summary_{tempfile.NamedTemporaryFile().name.split('/')[-1]}.pdf"
            )
            potential_output_path = os.path.join(output_dir, sanitized_filename)

        output_path = potential_output_path
        pdf.output(output_path)

        logger.info(f"📄 PDF generated: {output_path}")
        return output_path


# Singleton instance
pdf_maker = PDFMaker()
