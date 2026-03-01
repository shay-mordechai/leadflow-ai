# src/services/ai/whisper.py
import os
import logging
import tempfile
import httpx
from faster_whisper import WhisperModel

logger = logging.getLogger("WhisperService")

class WhisperService:
    def __init__(self):
        # We use the 'base' model for speed on CPU. 
        # Options: 'tiny', 'base', 'small', 'medium', 'large-v3'
        self.model_size = "base"
        self.model = None
        logger.info(f"Initializing Whisper Model ({self.model_size})...")

    def _load_model(self):
        """Lazy loading of the model to save memory during startup."""
        if self.model is None:
            # compute_type="int8" is optimized for CPU performance
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self.model

    async def transcribe_from_url(self, media_url: str) -> str:
        """
        Downloads a media file from a URL, transcribes it, and cleans up.
        """
        model = self._load_model()
        
        # 1. Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name

        try:
            # 2. Download the file from Twilio
            async with httpx.AsyncClient() as client:
                logger.info(f"📥 Downloading audio from: {media_url}")
                response = await client.get(media_url)
                if response.status_code != 200:
                    raise Exception(f"Failed to download audio: {response.status_code}")
                
                with open(tmp_path, "wb") as f:
                    f.write(response.content)

            # 3. Transcribe using faster-whisper
            logger.info("🎙️ Transcribing audio...")
            # beam_size=5 is a good balance between accuracy and speed
            segments, info = model.transcribe(tmp_path, beam_size=5, language="he")
            
            full_text = ""
            for segment in segments:
                full_text += segment.text + " "

            logger.info(f"✅ Transcription complete (Language: {info.language})")
            return full_text.strip()

        except Exception as e:
            logger.error(f"❌ Whisper Transcription Error: {e}")
            return "[Error: Could not transcribe audio]"

        finally:
            # 4. Clean up the temp file (Privacy & Storage)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.info(f"🧹 Temporary file {tmp_path} deleted.")

# Singleton instance
whisper_service = WhisperService()