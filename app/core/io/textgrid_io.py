"""
Модуль для работы с TextGrid (Praat) без привязки к GUI.
Использует библиотеку textgrid.
"""

import logging
import tempfile
from textgrid import TextGrid as TextGridFile, IntervalTier, PointTier, Point

from ...utils import decode_bytes

logger = logging.getLogger(__name__)

ALIGNMENT_TIER_NAMES = ["frames", "all frames", "dicom frames", "ultrasound frames"]


def load_textgrid(filepath: str) -> TextGridFile:
    """
    Загружает TextGrid из файла, автоматически обрабатывая проблемы с кодировкой.
    """
    try:
        return TextGridFile.fromFile(filepath)
    except Exception:
        # Пробуем перекодировать в UTF-8
        with open(filepath, "rb") as f:
            raw = f.read()
        text = decode_bytes(raw)
        if not text:
            raise ValueError("Не удалось декодировать TextGrid")
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(text.encode("utf-8"))
        tmp.close()
        return TextGridFile.fromFile(tmp.name)


def find_frame_tier_name(tg: TextGridFile) -> str | None:
    """Ищет имя слоя (tier) с кадрами."""
    for name in ALIGNMENT_TIER_NAMES:
        if name in tg.getNames():
            return name
    return None


def generate_frame_tier(
    tg: TextGridFile, frame_times: list[float], tier_name: str = "frames"
) -> None:
    """
    Добавляет в TextGrid точечный слой с временами кадров.
    :param tg: объект TextGrid
    :param frame_times: список времён для каждого кадра в секундах
    :param tier_name: желаемое имя слоя
    """
    # Удаляем существующий одноимённый слой, если он есть
    if tier_name in tg.getNames():
        tg.pop(tier_name)

    # Определяем максимальное время
    try:
        max_time = max(tg.maxTime, frame_times[-1])
    except AttributeError:
        max_time = frame_times[-1]

    tier = PointTier(tier_name, maxTime=max_time)
    for i, t in enumerate(frame_times):
        tier.addPoint(Point(t, str(i)))  # i – номер кадра, начиная с 0
    tg.append(tier)
    tg.maxTime = max_time


def extract_intervals(tg: TextGridFile, frame_tier_name: str = "frames") -> list[dict]:
    """
    Извлекает все интервалы из всех слоёв (кроме frame tier) в виде списка словарей,
    пригодного для поиска.
    Каждый словарь:
        - text: метка интервала
        - tier: имя слоя
        - file: имя файла (пока не заполняется, можно добавить позже)
        - start: время начала
        - end: время окончания
    """
    intervals = []
    for i, tier in enumerate(tg.tiers):
        if tier.name == frame_tier_name or tier.name == frame_tier_name + ".original":
            continue
        if isinstance(tier, IntervalTier):
            for interval in tier:
                if interval.mark:
                    intervals.append(
                        {
                            "text": interval.mark,
                            "tier": tier.name,
                            "file": "",  # будет заполнено, когда узнаем имя файла
                            "start": interval.minTime,
                            "end": interval.maxTime,
                        }
                    )
    return intervals
