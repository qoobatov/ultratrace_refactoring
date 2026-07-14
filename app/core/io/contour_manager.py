"""
Pure trace and contour point manager.
Stores data in a human-readable traces.json file in the project folder,
so it stays directly accessible to users and third-party tools
(e.g. ultrapolaRplot) without requiring a database.
Independent of GUI.
"""

import json
import os
import logging
import random
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TRACES_FILENAME = "traces.json"
METADATA_FILENAME = "metadata.json"


class ContourManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self._lock = threading.Lock()  # защита от гонок при параллельных запросах
        self.traces_path = self._resolve_traces_path()
        self._data = self._load()

    # ----- Инициализация / связывание с metadata.json -----

    def _resolve_traces_path(self) -> str:
        """
        metadata.json остаётся главным: если он существует, читаем оттуда
        имя файла трасс (поле traces_file). Если поля нет — прописываем
        его туда, указывая на дефолтное имя traces.json.
        """
        metadata_path = os.path.join(self.data_path, METADATA_FILENAME)
        traces_filename = TRACES_FILENAME

        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Failed to read metadata.json: %s", e)
                metadata = {}

            if "traces_file" in metadata:
                traces_filename = metadata["traces_file"]
            else:
                metadata["traces_file"] = traces_filename
                self._atomic_write(metadata_path, metadata)
        else:
            # metadata.json ещё не создан directory crawl'ом — не создаём его
            # здесь принудительно, это ответственность discover_study_files.
            # Просто используем дефолтное имя.
            pass

        return os.path.join(self.data_path, traces_filename)

    def _load(self) -> dict:
        if not os.path.exists(self.traces_path):
            return {"default_trace": None, "traces": {}}
        try:
            with open(self.traces_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("default_trace", None)
            data.setdefault("traces", {})
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load traces.json, starting fresh: %s", e)
            return {"default_trace": None, "traces": {}}

    def _save(self):
        self._atomic_write(self.traces_path, self._data)

    @staticmethod
    def _atomic_write(path: str, data: dict):
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)  # атомарно на большинстве ОС

    # ----- Работа с трассами -----

    def trace_names(self) -> List[str]:
        with self._lock:
            return list(self._data["traces"].keys())

    def create_trace(self, name: str, color: Optional[str] = None) -> dict:
        if not name:
            raise ValueError("Trace name cannot be empty")
        with self._lock:
            if name in self._data["traces"]:
                raise ValueError(f"Trace '{name}' already exists")
            if color is None:
                color = self._random_color()
            self._data["traces"][name] = {"color": color, "frames": {}}
            if self._data["default_trace"] is None:
                self._data["default_trace"] = name
            self._save()
        logger.info("Created trace '%s'", name)
        return {"color": color, "frames": {}}

    def rename_trace(self, old_name: str, new_name: str) -> dict:
        with self._lock:
            self._require_trace(old_name)
            if new_name in self._data["traces"]:
                raise ValueError(f"Trace '{new_name}' already exists")
            self._data["traces"][new_name] = self._data["traces"].pop(old_name)
            if self._data["default_trace"] == old_name:
                self._data["default_trace"] = new_name
            self._save()
        return {"color": self._data["traces"][new_name]["color"]}

    def delete_trace(self, name: str):
        with self._lock:
            self._require_trace(name)
            del self._data["traces"][name]
            if self._data["default_trace"] == name:
                remaining = list(self._data["traces"].keys())
                self._data["default_trace"] = remaining[0] if remaining else None
            self._save()
        logger.info("Deleted trace '%s'", name)

    def get_default_trace(self) -> Optional[str]:
        with self._lock:
            default = self._data["default_trace"]
            if default and default in self._data["traces"]:
                return default
            names = list(self._data["traces"].keys())
            return names[0] if names else None

    def set_default_trace(self, name: str):
        with self._lock:
            self._require_trace(name)
            self._data["default_trace"] = name
            self._save()

    def recolor_trace(self, name: str, color: str):
        with self._lock:
            self._require_trace(name)
            self._data["traces"][name]["color"] = color
            self._save()

    def get_trace_color(self, name: str) -> str:
        with self._lock:
            self._require_trace(name)
            return self._data["traces"][name]["color"]

    # ----- Работа с точками -----

    def get_points(self, trace_name: str, frame_number: int) -> List[dict]:
        with self._lock:
            self._require_trace(trace_name)
            frames = self._data["traces"][trace_name]["frames"]
            return list(frames.get(str(frame_number), []))

    def set_points(self, trace_name: str, frame_number: int, points: List[dict]):
        """Заменяет все точки кадра целиком."""
        with self._lock:
            self._require_trace(trace_name)
            frames = self._data["traces"][trace_name]["frames"]
            key = str(frame_number)
            if points:
                frames[key] = [{"x": p["x"], "y": p["y"]} for p in points]
            else:
                frames.pop(key, None)
            self._save()

    def add_point(
        self, trace_name: str, frame_number: int, x: float, y: float
    ) -> List[dict]:
        with self._lock:
            self._require_trace(trace_name)
            frames = self._data["traces"][trace_name]["frames"]
            key = str(frame_number)
            frames.setdefault(key, []).append({"x": x, "y": y})
            self._save()
            return list(frames[key])

    def clear_frame(self, trace_name: str, frame_number: int):
        with self._lock:
            self._require_trace(trace_name)
            self._data["traces"][trace_name]["frames"].pop(str(frame_number), None)
            self._save()

    def clear_trace(self, trace_name: str):
        with self._lock:
            self._require_trace(trace_name)
            self._data["traces"][trace_name]["frames"] = {}
            self._save()

    def get_all_points(self) -> List[dict]:
        """Возвращает все точки всех трасс — для экспорта."""
        with self._lock:
            result = []
            for trace_name, trace in self._data["traces"].items():
                for frame_key, pts in trace["frames"].items():
                    frame = int(frame_key)
                    for p in pts:
                        result.append(
                            {
                                "trace": trace_name,
                                "frame": frame,
                                "x": p["x"],
                                "y": p["y"],
                            }
                        )
            result.sort(key=lambda r: (r["trace"], r["frame"]))
            return result

    def get_annotated_frame_count(self, trace_name: str) -> int:
        """Количество кадров с хотя бы одной точкой."""
        with self._lock:
            self._require_trace(trace_name)
            return len(self._data["traces"][trace_name]["frames"])

    # ----- Утилиты -----

    def _require_trace(self, name: str):
        if name not in self._data["traces"]:
            raise KeyError(f"Trace '{name}' not found")

    def _random_color(self) -> str:
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    @property
    def colors(self) -> Dict[str, str]:
        with self._lock:
            return {name: t["color"] for name, t in self._data["traces"].items()}
