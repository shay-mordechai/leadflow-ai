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
        # We use the 'base' model for a good balance of speed and accuracy on CPU.
        self.model_size = "base"
        self.model = None
        logger.info(f"Initializing Whisper Service. Model '{self.model_size}' will be lazy-loaded.")

    def _load_model(self):
        """Lazy loading of the model to save memory during startup."""
        if self.model is None:
            logger.info("loading Whisper Model into memory (or swap)...")
            # OPTIMIZATION FOR LOW RAM / SWAP:
            # - compute_type="int8": Reduces memory footprint by ~50%.
            # - cpu_threads=2: Prevents CPU thrashing on micro instances.
            # - num_workers=1: Ensures only one transcription runs concurrently.
            self.model = WhisperModel(
                self.model_size, 
                device="cpu", 
                compute_type="int8",
                cpu_threads=2,
                num_workers=1
            )
            logger.info("✅ Whisper Model Loaded successfully.")
        return self.model

    def _transcribe_sync(self, file_path: str) -> str:
        """
        Synchronous transcription logic optimized for long files.
        """
        try:
            model = self._load_model()
            
            # VAD_FILTER is crucial for long files! 
            # It skips silent parts, saving massive amounts of processing time and memory.
            segments, info = model.transcribe(
                file_path, 
                beam_size=5, 
                language="he",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            logger.info(f"🎙️ Transcription started. Detected language: {info.language}")
            
            # Use a generator approach to build the string to avoid huge memory spikes
            # if the file is an hour long.
            full_text = []
            for segment in segments:
                full_text.append(segment.text)
                
            final_text = " ".join(full_text).strip()
            logger.info(f"✅ Transcription complete. Length: {len(final_text)} characters.")
            
            return final_text
            
        except Exception as e:
            logger.error(f"🔥 Transcription error inside sync worker: {e}")
            raise e

    async def transcribe_from_url(self, media_url: str) -> str:
        """
        Downloads a media file from a URL, transcribes it non-blockingly, and cleans up.
        (Used primarily for short WhatsApp voice notes)
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                logger.info(f"📥 Downloading audio from URL: {media_url}")
                response = await client.get(media_url)
                
                if response.status_code != 200:
                    raise Exception(f"Failed to download audio: HTTP {response.status_code}")
                
                with open(tmp_path, "wb") as f:
                    f.write(response.content)

            # Transcribe without blocking the event loop
            full_text = await asyncio.to_thread(self._transcribe_sync, tmp_path)
            return full_text

        except Exception as e:
            logger.error(f"❌ URL Transcription Error: {e}")
            return "[Error: Could not transcribe audio from URL]"

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def transcribe_local_file(self, file_path: str) -> str:
        """
        Transcribes an existing local file (Used for large files uploaded via Dashboard).
        The caller is responsible for deleting the file after processing.
        """
        logger.info(f"🎧 Starting transcription for local file: {file_path}")
        try:
            full_text = await asyncio.to_thread(self._transcribe_sync, file_path)
            return full_text
        except Exception as e:
            logger.error(f"❌ Local File Transcription Error: {e}")
            return f"[Error processing file: {str(e)}]"

# Singleton instance
whisper_service = WhisperService()