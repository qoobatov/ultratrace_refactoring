"""
Audio file loading and extraction of basic information.
Does not use pyaudio or tkinter.
"""

import logging
from pydub import AudioSegment
from typing import Optional

logger = logging.getLogger(__name__)


class AudioReader:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.segment: Optional[AudioSegment] = None
        self.duration: float = 0.0
        self.sample_width: int = 0
        self.channels: int = 0
        self.frame_rate: int = 0
        self._loaded = False

    def load(self):
        """Loads an audio file and saves metadata."""
        try:
            self.segment = AudioSegment.from_file(self.filepath)
            self.duration = len(self.segment) / 1000.0
            self.sample_width = self.segment.sample_width
            self.channels = self.segment.channels
            self.frame_rate = self.segment.frame_rate
            self._loaded = True
            logger.info(f"Audio loaded: {self.filepath}, duration={self.duration:.2f}s")
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            raise

    @property
    def loaded(self) -> bool:
        return self._loaded

    def get_segment_bytes(
        self, start_ms: int = 0, end_ms: Optional[int] = None
    ) -> bytes:
        """Возвращает сырые байты указанного сегмента в формате WAV."""
        if not self.segment:
            raise RuntimeError("Audio not loaded")
        seg = self.segment[start_ms:end_ms] if end_ms else self.segment[start_ms:]
        return seg.raw_data  # можно экспортировать в WAV, но для сырых данных лучше raw
