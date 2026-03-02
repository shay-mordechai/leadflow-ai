# src/services/ai/whisper.py
import os
import logging
import tempfile
import httpx
import asyncio
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

    def _transcribe_sync(self, tmp_path: str) -> str:
        """
        Synchronous transcription logic.
        This is separated so it can be run in a threadpool, preventing server freezes.
        """
        model = self._load_model()
        # beam_size=5 is a good balance between accuracy and speed
        segments, info = model.transcribe(tmp_path, beam_size=5, language="he")
        
        full_text = "".join([segment.text + " " for segment in segments])
        logger.info(f"✅ Transcription complete (Language: {info.language})")
        
        return full_text.strip()

    async def transcribe_from_url(self, media_url: str) -> str:
        """
        Downloads a media file from a URL, transcribes it non-blockingly, and cleans up.
        """
        # 1. Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name

        try:
            # 2. Download the file from Twilio
            # CRITICAL: follow_redirects=True is required because Twilio redirects media to AWS S3.
            async with httpx.AsyncClient(follow_redirects=True) as client:
                logger.info(f"📥 Downloading audio from: {media_url}")
                response = await client.get(media_url)
                
                if response.status_code != 200:
                    raise Exception(f"Failed to download audio: HTTP {response.status_code}")
                
                with open(tmp_path, "wb") as f:
                    f.write(response.content)

            # 3. Transcribe using faster-whisper (Non-blocking)
            logger.info("🎙️ Transcribing audio...")
            
            # CRITICAL: Run the CPU-heavy transcription in a background thread
            # so we don't block the FastAPI event loop!
            full_text = await asyncio.to_thread(self._transcribe_sync, tmp_path)
            
            return full_text

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