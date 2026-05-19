"""
Pure trace and contour point manager.
Stores data in a traces.json file in the project folder.
Independent of GUI.
"""

import json
import os
import logging
import random
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContourManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.storage_file = os.path.join(data_path, "traces.json")
        # Structure:
        # {
        #   "default_trace": "trace1",
        #   "traces": {
        #     "trace1": {
        #       "color": "#rrggbb",
        #       "frames": {
        #         "1": [{"x": 0.1, "y": 0.2}, ...],
        #         "2": [...], ...
        #       }
        #     }, ...
        #   }
        # }
        self.data = {"default_trace": None, "traces": {}}
        self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    self.data = json.load(f)
                logger.info("Loaded traces from %s", self.storage_file)
            except Exception as e:
                logger.error("Failed to load traces: %s", e)
                # оставляем пустую структуру
        else:
            logger.info("No traces file found, starting fresh.")

    def _save(self):
        with open(self.storage_file, "w") as f:
            json.dump(self.data, f, indent=2)

    # ----- Работа с трассами -----

    def trace_names(self) -> List[str]:
        return list(self.data["traces"].keys())

    def create_trace(self, name: str, color: Optional[str] = None) -> dict:
        """Creates a new trace and returns its data."""
        if not name:
            raise ValueError("Trace name cannot be empty")
        if name in self.data["traces"]:
            raise ValueError(f"Trace '{name}' already exists")
        if color is None:
            color = self._random_color()
        self.data["traces"][name] = {"color": color, "frames": {}}
        self._save()
        logger.info("Created trace '%s'", name)
        return self.data["traces"][name]

    def rename_trace(self, old_name: str, new_name: str) -> dict:
        if new_name in self.data["traces"]:
            raise ValueError(f"Trace '{new_name}' already exists")
        if old_name not in self.data["traces"]:
            raise KeyError(f"Trace '{old_name}' not found")
        self.data["traces"][new_name] = self.data["traces"].pop(old_name)
        if self.data["default_trace"] == old_name:
            self.data["default_trace"] = new_name
        self._save()
        return self.data["traces"][new_name]

    def delete_trace(self, name: str):
        if name not in self.data["traces"]:
            raise KeyError(f"Trace '{name}' not found")
        del self.data["traces"][name]
        if self.data["default_trace"] == name:
            self.data["default_trace"] = next(iter(self.data["traces"]), None)
        self._save()
        logger.info("Deleted trace '%s'", name)

    def get_trace(self, name: str) -> dict:
        return self.data["traces"][name]

    def get_default_trace(self) -> str:
        return self.data["default_trace"] or (
            self.trace_names()[0] if self.trace_names() else None
        )

    def set_default_trace(self, name: str):
        if name not in self.data["traces"]:
            raise KeyError(f"Trace '{name}' not found")
        self.data["default_trace"] = name
        self._save()

    def recolor_trace(self, name: str, color: str):
        if name not in self.data["traces"]:
            raise KeyError(f"Trace '{name}' not found")
        self.data["traces"][name]["color"] = color
        self._save()

    # ----- Working with points on a specific frame -----

    def get_points(self, trace_name: str, frame_number: int) -> List[dict]:
        frame_key = str(frame_number)
        trace = self.data["traces"].get(trace_name)
        if not trace:
            return []
        return trace["frames"].get(frame_key, [])

    def set_points(self, trace_name: str, frame_number: int, points: List[dict]):
        """Saves points for a frame. Each point: {"x": float, "y": float}."""
        trace = self.data["traces"][trace_name]
        trace["frames"][str(frame_number)] = points
        self._save()

    def add_point(
        self, trace_name: str, frame_number: int, x: float, y: float
    ) -> List[dict]:
        """Adds a single point and returns the updated list."""
        points = self.get_points(trace_name, frame_number)
        points.append({"x": x, "y": y})
        self.set_points(trace_name, frame_number, points)
        return points

    def clear_frame(self, trace_name: str, frame_number: int):
        trace = self.data["traces"].get(trace_name)
        if trace and str(frame_number) in trace["frames"]:
            del trace["frames"][str(frame_number)]
            self._save()

    def clear_trace(self, trace_name: str):
        trace = self.data["traces"].get(trace_name)
        if trace:
            trace["frames"] = {}
            self._save()

    # ----- Utilities -----

    def _random_color(self):
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    def get_trace_color(self, name: str) -> str:
        return self.data["traces"][name]["color"]
