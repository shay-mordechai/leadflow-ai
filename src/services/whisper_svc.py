# Professional English Comment:
# Configuration and helper logic for the Faster-Whisper transcription service.
# Centralizes model parameters and file constraints.
# Also contains the prompt engineering logic for the LLM summarization.

from src.config import settings

class WhisperConfig:
    """
    Centralized configuration for audio transcription.
    Defines supported formats and model parameters to ensure consistency
    between the API uploads and the Celery Worker processing.
    """

    # Audio processing constraints
    SUPPORTED_FORMATS = {"mp3", "mp4", "wav", "m4a", "aac"}
    MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500MB Limit

    # AI Model Parameters
    # 'medium' offers a good balance between speed and Hebrew accuracy
    MODEL_SIZE = "medium"
    DEVICE = "cpu"  # Change to "cuda" if GPU is available in the deployment environment
    COMPUTE_TYPE = "int8" # Quantization for performance

    # Transcription Settings
    DEFAULT_LANGUAGE = "he"  # Optimized for Hebrew coaching sessions
    BEAM_SIZE = 5

    @staticmethod
    def is_supported_format(filename: str) -> bool:
        """Checks if the file extension is supported."""
        if '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in WhisperConfig.SUPPORTED_FORMATS

    @staticmethod
    def get_summary_prompt() -> str:
        """
        Returns the system prompt for the LLM summarization.
        Maintains the specific Hebrew tone required for the coaching persona.
        """
        return """
        Please create a comprehensive summary of this coaching session in Hebrew.
        Structure the summary as follows:

        ## סיכום פגישת קואצ'ינג - {date}

        ### 📋 נושאים מרכזיים שנדונו:
        - [List main topics]

        ### 🎯 יעדים שהוגדרו:
        - [List goals]

        ### 💡 תובנות מרכזיות:
        - [Key insights]

        ### 📝 משימות לביצוע:
        - [Action items]

        ### 🔍 נקודות להעמקה:
        - [Topics for future sessions]

        ### 📅 הכנה לפגישה הבאה:
        - [Preparation items]

        אנא כתוב בצורה ברורה, מקצועית ומעשית. התמקד בתובנות ופעולות קונקרטיות.
        """
