import os
import logging
from PIL import Image
from .io.framereader import READERS, LABEL_TO_READER, DicomPNGReader
from .io.textgrid_io import (
    load_textgrid,
    find_frame_tier_name,
    generate_frame_tier,
    extract_intervals,
)
from .io.audio_reader import AudioReader
from .io.contour_manager import ContourManager
from .io.file_discovery import discover_study_files
from .search_service import search_intervals

logger = logging.getLogger(__name__)

US_TXT_SUFFIX = "US.txt"


class StudySession:
    def __init__(self, data_path: str):
        self.data_path = os.path.abspath(data_path)
        self.file_sets = discover_study_files(self.data_path)
        if not self.file_sets:
            raise FileNotFoundError(f"No valid study files found in {self.data_path}")

        self.current_file_index = 0
        self.current_file = self.file_sets[self.current_file_index]

        self.contours = ContourManager(self.data_path)
        self.offset = self._load_offset()
        self._original_frame_times = []

        self.reader = None
        self.mode = None
        self._current_method_label = None  # метка текущего метода
        self._reader_cache = {}  # {(file_index, method_label): reader}
        self.audio_reader = None
        self.textgrid = None
        self.frame_tier_name = None
        self._init_current_file()

    def _load_offset(self):
        offset_file = os.path.join(self.data_path, "offset.txt")
        if os.path.exists(offset_file):
            try:
                with open(offset_file, "r") as f:
                    return float(f.read().strip())
            except:
                return 0.0
        return 0.0

    def _save_offset(self):
        offset_file = os.path.join(self.data_path, "offset.txt")
        with open(offset_file, "w") as f:
            f.write(str(self.offset))

    def set_frame_offset(self, offset_ms: float):
        """Установить смещение кадров относительно аудио (в миллисекундах)."""
        self.offset = offset_ms / 1000.0
        self._save_offset()
        if self.textgrid and self._original_frame_times:
            new_times = [t + self.offset for t in self._original_frame_times]
            generate_frame_tier(
                self.textgrid, new_times, self.frame_tier_name or "frames"
            )
            self.frame_tier_name = (
                find_frame_tier_name(self.textgrid) or self.frame_tier_name
            )

    def _init_current_file(self):
        ext = self.current_file["extensions"]

        self.mode = None
        if ".dicom" in ext:
            self.mode = "dicom"
            self.dicom_path = os.path.join(self.data_path, ext[".dicom"])
        elif ".ult" in ext and US_TXT_SUFFIX in ext:
            self.mode = "ult"
            self.ult_path = os.path.join(self.data_path, ext[".ult"])
            self.us_txt_path = os.path.join(self.data_path, ext[US_TXT_SUFFIX])
        else:
            raise ValueError("Unsupported file set")

        # Используем тот же метод что был активен, либо дефолтный
        default_cls = READERS[self.mode][0]
        if (
            self._current_method_label
            and self._current_method_label in LABEL_TO_READER.get(self.mode, {})
        ):
            default_cls = LABEL_TO_READER[self.mode][self._current_method_label]
        self._set_reader(default_cls)

        # Сохраняем оригинальные времена кадров до применения offset
        if self.reader:
            try:
                self._original_frame_times = self.reader.getFrameTimes()
            except:
                self._original_frame_times = []

        # Аудио
        audio_ext = next(
            (e for e in [".wav", ".flac", ".ogg", ".mp3"] if e in ext), None
        )
        self.audio_reader = None
        if audio_ext:
            audio_path = os.path.join(self.data_path, ext[audio_ext])
            self.audio_reader = AudioReader(audio_path)
            try:
                self.audio_reader.load()
            except Exception:
                logger.warning("Failed to load audio, continuing without it.")
                self.audio_reader = None

        # TextGrid
        self.textgrid = None
        self.frame_tier_name = None
        tg_rel = ext.get(".TextGrid")
        if tg_rel:
            tg_path = os.path.join(self.data_path, tg_rel)
            self.textgrid = load_textgrid(tg_path)
        else:
            max_time = 1.0
            if self._original_frame_times:
                max_time = max(self._original_frame_times) + self.offset
            from textgrid import TextGrid as TGFile, IntervalTier

            self.textgrid = TGFile(maxTime=max_time)
            sentence_tier = IntervalTier("sentence")
            sentence_tier.add(0, max_time, "")
            self.textgrid.append(sentence_tier)

        self.frame_tier_name = find_frame_tier_name(self.textgrid)
        if not self.frame_tier_name:
            frame_times = self.get_frame_times()
            if frame_times:
                generate_frame_tier(self.textgrid, frame_times)
                self.frame_tier_name = "frames"

    def _set_reader(self, reader_cls):
        """Устанавливает ридер, используя кеш если доступен."""
        label = reader_cls.label
        cache_key = (self.current_file_index, label)

        if cache_key in self._reader_cache:
            self.reader = self._reader_cache[cache_key]
            self._current_method_label = label
            logger.debug("Reader cache hit: %s", cache_key)
            return

        # Создаём новый ридер
        if self.mode == "dicom":
            processed = self.current_file.get("processed")
            if reader_cls == DicomPNGReader and processed:
                self.reader = DicomPNGReader(self.dicom_path, png_dir=self.data_path)
            else:
                self.reader = reader_cls(self.dicom_path)
        elif self.mode == "ult":
            self.reader = reader_cls(self.ult_path, self.us_txt_path)
        else:
            self.reader = None

        if self.reader:
            self._reader_cache[cache_key] = self.reader
        self._current_method_label = label
        logger.debug("Reader cache miss, created: %s", cache_key)

    def _ensure_reader_loaded(self):
        if self.reader and not self.reader.loaded:
            self.reader.load()

    def _clear_reader_cache(self):
        """Очищает кеш ридеров — вызывается при смене метода."""
        self._reader_cache.clear()
        logger.debug("Reader cache cleared")

    # ---------- Основные методы ----------
    def list_files(self):
        result = []
        for i, fset in enumerate(self.file_sets):
            result.append(
                {
                    "index": i,
                    "name": fset["name"],
                    "audio_relpath": fset.get("audio_relpath"),
                    "extensions": list(fset["extensions"].keys()),
                }
            )
        return result

    def switch_file(self, index: int):
        if index < 0 or index >= len(self.file_sets):
            raise IndexError("File index out of range")
        self.current_file_index = index
        self.current_file = self.file_sets[index]
        self.offset = self._load_offset()
        self._original_frame_times = []
        self._init_current_file()

    def get_frame(self, index: int) -> Image.Image:
        if not self.reader:
            raise RuntimeError("Reader not initialized")
        self._ensure_reader_loaded()
        img = self.reader.getFrame(index)
        if img is None:
            raise ValueError(f"Frame {index} not found")
        return img

    def get_frame_times(self) -> list:
        if self._original_frame_times:
            return [t + self.offset for t in self._original_frame_times]
        if self.reader:
            self._ensure_reader_loaded()
            return self.reader.getFrameTimes()
        return []

    def available_methods(self) -> list:
        if self.mode:
            return [cls.label for cls in READERS[self.mode]]
        return []

    def change_method(self, method_label: str):
        if self.mode and method_label in LABEL_TO_READER[self.mode]:
            cls = LABEL_TO_READER[self.mode][method_label]
            # Метод меняется глобально — кеш всех файлов устарел
            self._clear_reader_cache()
            self._set_reader(cls)
        else:
            raise ValueError(f"Unknown method: {method_label}")

    # TextGrid
    def get_all_intervals(self) -> list:
        if not self.textgrid:
            return []
        intervals = extract_intervals(self.textgrid, self.frame_tier_name)
        fname = os.path.basename(self.current_file["name"])
        for iv in intervals:
            iv["file"] = fname
        return intervals

    def search(self, pattern: str, context_size: int = 3) -> list:
        return search_intervals(self.get_all_intervals(), pattern, context_size)

    # Аудио
    def get_audio_filepath(self) -> str | None:
        if self.audio_reader and self.audio_reader.loaded:
            return self.audio_reader.filepath
        return None

    def get_audio_duration(self) -> float | None:
        if self.audio_reader:
            return self.audio_reader.duration
        return None

    # Контуры
    def get_trace_names(self):
        return self.contours.trace_names()

    def create_trace(self, name, color=None):
        return self.contours.create_trace(name, color)

    def delete_trace(self, name):
        self.contours.delete_trace(name)

    def rename_trace(self, old, new):
        return self.contours.rename_trace(old, new)

    def get_default_trace(self):
        return self.contours.get_default_trace()

    def set_default_trace(self, name):
        self.contours.set_default_trace(name)

    def get_trace_points(self, trace_name, frame_number):
        return self.contours.get_points(trace_name, frame_number)

    def save_trace_points(self, trace_name, frame_number, points):
        self.contours.set_points(trace_name, frame_number, points)

    def clear_trace_points(self, trace_name, frame_number):
        self.contours.clear_frame(trace_name, frame_number)

    def clear_all_trace_points(self, trace_name):
        self.contours.clear_trace(trace_name)

    def recolor_trace(self, name, color):
        self.contours.recolor_trace(name, color)
