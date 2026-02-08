# src/services/media/transcription.py
import os
import logging
import whisper

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

# Singleton instance
transcriber = TranscriberService()