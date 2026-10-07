# src/services/ai/whisper.py
import os
import logging
import tempfile
import httpx
import asyncio
from urllib.parse import urlsplit
from pathlib import Path
from faster_whisper import WhisperModel

logger = logging.getLogger("WhisperService")
LOCAL_AUDIO_ROOT = Path("storage/audio").resolve()
MAX_REMOTE_AUDIO_SIZE = 25 * 1024 * 1024
_REMOTE_AUDIO_SUFFIXES = {
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-m4a": ".m4a",
}


def _is_approved_media_url(media_url: str) -> bool:
    """Allow HTTPS media fetches only from provider-controlled media domains."""
    try:
        parsed = urlsplit(media_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return False

    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return False

    return (
        hostname.endswith(".twilio.com")
        or hostname in {"graph.facebook.com", "lookaside.fbsbx.com"}
        or hostname.endswith(".fbcdn.net")
    )

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
        Download bounded audio from an approved provider URL, transcribe, and clean up.
        """
        tmp_path: str | None = None
        try:
            if not _is_approved_media_url(media_url):
                raise ValueError("Media URL host is not approved")

            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=7.0,
            ) as client:
                async with client.stream("GET", media_url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    media_type = content_type.split(";", 1)[0].strip().lower()
                    suffix = _REMOTE_AUDIO_SUFFIXES.get(media_type)
                    if suffix is None:
                        raise ValueError("Unsupported remote audio media type")

                    declared_length = response.headers.get("content-length")
                    if declared_length is not None:
                        try:
                            if int(declared_length) > MAX_REMOTE_AUDIO_SIZE:
                                raise ValueError("Remote audio exceeds maximum size")
                        except ValueError as error:
                            raise ValueError("Invalid or oversized remote audio length") from error

                    total_bytes = 0
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_path = tmp_file.name
                        async for chunk in response.aiter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > MAX_REMOTE_AUDIO_SIZE:
                                raise ValueError("Remote audio exceeds maximum size")
                            tmp_file.write(chunk)

                    if total_bytes == 0:
                        raise ValueError("Remote audio body is empty")

            # Transcribe without blocking the event loop
            full_text = await asyncio.to_thread(self._transcribe_sync, tmp_path)
            return full_text

        except (httpx.HTTPError, ValueError, OSError) as error:
            logger.error("❌ URL Transcription Error (%s)", type(error).__name__)
            return "[Error: Could not transcribe audio from URL]"

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def transcribe_local_file(self, file_path: str) -> str:
        """
        Transcribes an existing local file (Used for large files uploaded via Dashboard).
        The caller is responsible for deleting the file after processing.
        """
        candidate_path = Path(file_path).resolve()
        if not candidate_path.is_relative_to(LOCAL_AUDIO_ROOT) or not candidate_path.is_file():
            logger.warning("Rejected local transcription request outside the audio upload directory.")
            return "[Error: Invalid media path]"

        logger.info("🎧 Starting transcription for validated local audio.")
        try:
            full_text = await asyncio.to_thread(self._transcribe_sync, str(candidate_path))
            return full_text
        except Exception as e:
            logger.error("❌ Local File Transcription Error (%s)", type(e).__name__)
            return "[Error processing local audio]"

# Singleton instance
whisper_service = WhisperService()