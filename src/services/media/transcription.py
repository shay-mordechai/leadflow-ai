# src/services/transcription.py
import os
import logging
import whisper
from fpdf import FPDF

# Configure Logger
logger = logging.getLogger("Transcriber")

class TranscriberService:
    """
    Service for transcribing audio files using OpenAI Whisper.
    Optimized for CPU usage on t3.micro instances.
    """
    def __init__(self):
        # We use the 'base' model. 
        # 'tiny' is faster but less accurate. 'small' might crash t3.micro RAM.
        self.model_size = "base" 
        self.model = None

    def _load_model(self):
        """
        Lazy loading of the model to save startup time.
        """
        if not self.model:
            logger.info(f"🎙️ Loading Whisper Model ({self.model_size})...")
            # fp16=False is crucial for CPU inference (prevents warnings/errors)
            self.model = whisper.load_model(self.model_size)
            logger.info("✅ Whisper Model Loaded!")

    def transcribe_audio(self, file_path: str) -> dict:
        """
        Transcribes the given audio file.
        Returns a dictionary with text and language.
        """
        if not os.path.exists(file_path):
            logger.error(f"❌ Audio file missing: {file_path}")
            return {"text": "", "error": "File not found"}

        self._load_model()
        
        logger.info(f"🎧 Starting transcription: {file_path}")
        try:
            # Transcribe
            result = self.model.transcribe(file_path, fp16=False)
            
            text = result.get("text", "").strip()
            language = result.get("language", "unknown")
            
            logger.info(f"📝 Transcription complete ({len(text)} chars)")
            return {
                "text": text,
                "language": language
            }
        except Exception as e:
            logger.error(f"🔥 Transcription failed: {e}")
            return {"text": "", "error": str(e)}

class PDFMaker:
    """
    Service for generating simple PDF reports (Meeting Summaries / Receipts).
    """
    def create_meeting_summary(self, summary_text: str, filename: str) -> str:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Font handling:
        # Standard fonts (Arial) don't support Hebrew. 
        # Ideally, we should load a TTF font like DejaVuSans.
        # For this MVP, we use standard font and handle encoding gracefully.
        pdf.set_font("Arial", size=12)
        
        pdf.cell(200, 10, txt="Meeting Summary", ln=True, align='C')
        pdf.ln(10)
        
        # Add text content
        # Note: Hebrew might appear reversed or as ??? without a proper TTF font file.
        # We encode to latin-1 to prevent crashes on non-ascii characters.
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

# Expose instances for import in webhooks.py
transcriber = TranscriberService()
pdf_maker = PDFMaker()