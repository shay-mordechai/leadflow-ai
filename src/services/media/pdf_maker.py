# src/services/media/pdf_maker.py
import os
import logging
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
        
        pdf.cell(200, 10, txt="Meeting Summary", ln=True, align='C')
        pdf.ln(10)
        
        # Add text content
        # We encode to latin-1 to prevent crashes on non-ascii characters (Hebrew placeholder)
        # In a production environment, you should load a UTF-8 compatible font (e.g., DejaVuSans).
        safe_text = summary_text.encode('latin-1', 'replace').decode('latin-1')
        
        for line in safe_text.split('\n'):
            pdf.multi_cell(0, 10, txt=line)
        
        # Ensure storage directory exists
        output_dir = "storage/pdfs"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, filename)
        pdf.output(output_path)
        
        logger.info(f"📄 PDF generated: {output_path}")
        return output_path

# Singleton instance
pdf_maker = PDFMaker()