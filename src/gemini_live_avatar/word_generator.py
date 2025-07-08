import os
import tempfile
import wave

import torch
import whisperx
import logging
from functools import lru_cache
from gemini_live_avatar.singleton import Singleton

logger = logging.getLogger(__name__)

class WordGenerator(metaclass=Singleton):
    def __init__(self, model_size: str = "small", compute_type: str = "float32"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"📥 Loading Whisper model on {self.device}")
        self.model = whisperx.load_model(model_size, device=self.device, compute_type=compute_type)

    def generate_from_bytes(self, audio_bytes: bytes) -> dict:
        """
        Accepts raw PCM audio bytes (mono, 16-bit, 24000Hz), wraps them in a proper WAV file,
        and performs transcription and alignment.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp_path = tmp.name

        try:
            # Write the WAV file with proper header
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)  # mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(24000)  # 24 kHz
                wf.writeframes(audio_bytes)
            return self.generate(tmp_path)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def generate(self, audio_path: str) -> dict:
        logger.info("🧠 Transcribing audio...")
        result = self.model.transcribe(audio_path)
        segments = result.get("segments", [])
        if not segments:
            raise ValueError("❌ No segments found in transcription. Check the audio quality.")

        logger.info("🔠 Transcribed segments:")
        for seg in segments:
            logger.debug(f" - [{seg['start']} - {seg['end']}] {seg['text']}")

        language = result["language"]
        logger.info(f"🎯 Getting alignment model for language: {language}")
        align_model, metadata = self.get_alignment_model(language, self.device)

        logger.info("📌 Performing phoneme alignment...")
        aligned = whisperx.align(
            segments,
            align_model,
            metadata,
            audio_path,
            self.device,
            return_char_alignments=False
        )

        logger.info("🧩 Parsing aligned phonemes...")
        return self._parse_alignment(aligned)

    @staticmethod
    @lru_cache(maxsize=4)
    def get_alignment_model(language: str, device: str):
        logger.info(f"📦 Loading alignment model for language: {language}")
        return whisperx.load_align_model(language_code=language, device=device)

    def _parse_alignment(self, aligned_data: dict) -> dict:
        words_buffer = {
            "words": [],
            "wtimes": [],
            "wdurations": []
        }

        for segment in aligned_data.get("segments", []):
            for word in segment.get("words", []):
                word_text = word["word"]
                start = float(word["start"])
                end = float(word["end"])

                words_buffer["words"].append(word_text)
                words_buffer["wtimes"].append(int(start * 1000))
                words_buffer["wdurations"].append(int((end - start) * 1000))

        return words_buffer
