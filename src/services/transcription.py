# src/services/transciption.py
import os
import logging
from faster_whisper import WhisperModel
# Assuming you have these in your config, otherwise use strings directly
try:
    from src.config import settings
    MODEL_SIZE = getattr(settings, "WHISPER_MODEL_SIZE", "tiny")
    DEVICE = getattr(settings, "WHISPER_DEVICE", "cpu")
    COMPUTE_TYPE = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")
except ImportError:
    # Fallback defaults
    MODEL_SIZE = "tiny" 
    DEVICE = "cpu"
    COMPUTE_TYPE = "int8"

# Setup Logger
logger = logging.getLogger(__name__)

print(f"🔊 Loading Whisper Model ({MODEL_SIZE}) on {DEVICE}...")

# Load the model once at module level to save time on subsequent calls
# 'int8' is crucial for running on low-RAM instances like EC2 t3.micro
try:
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("✅ Whisper Model Loaded successfully!")
except Exception as e:
    logger.critical(f"Failed to load Whisper model: {e}")
    raise e

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes an audio file using the pre-loaded Whisper model.
    
    Args:
        file_path (str): The absolute path to the audio file.
        
    Returns:
        str: The combined transcribed text.
        
    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(file_path):
        logger.error(f"Audio file not found: {file_path}")
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    logger.info(f"Starting transcription for: {file_path}")
    
    # beam_size=5 provides better accuracy at the cost of slight speed
    segments, info = model.transcribe(file_path, beam_size=5)
    
    logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")

    # Combine segments into a single string
    full_text = " ".join([segment.text for segment in segments])
    return full_text.strip()