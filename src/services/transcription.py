from faster_whisper import WhisperModel
import os

class TranscriptionService:
    def __init__(self):
        self.model = None
        # נשתמש במודל הקטן ביותר לביצועים מקסימליים בשרת חלש
        self.model_size = "tiny"

    def transcribe(self, audio_path: str):
        if self.model is None:
            # טעינת המודל רק כשמגיעה ההקלטה הראשונה
            # device="cpu" כי אין לנו כרטיס מסך ב-EC2
            # compute_type="int8" חוסך המון RAM (קוונטיזציה)
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")

        segments, info = self.model.transcribe(audio_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip()

transcription_service = TranscriptionService()
