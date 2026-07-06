"""
Pure trace and contour point manager.
Stores data in a SQLite database (traces.db) in the project folder.
Migrates automatically from traces.json if present.
Independent of GUI.
"""

import json
import os
import sqlite3
import logging
import random
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    name        TEXT PRIMARY KEY,
    color       TEXT NOT NULL,
    is_default  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS points (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_name  TEXT NOT NULL REFERENCES traces(name) ON DELETE CASCADE ON UPDATE CASCADE,
    frame       INTEGER NOT NULL,
    x           REAL NOT NULL,
    y           REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_points_trace_frame ON points(trace_name, frame);
"""


class ContourManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.db_path = os.path.join(data_path, "traces.db")
        self.json_path = os.path.join(data_path, "traces.json")

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

        self._migrate_from_json()

    def _migrate_from_json(self):
        """Мигрирует данные из traces.json если БД пустая и json существует."""
        if not os.path.exists(self.json_path):
            return
        row = self.conn.execute("SELECT COUNT(*) FROM traces").fetchone()
        if row[0] > 0:
            return  # БД уже заполнена — пропускаем

        logger.info("Migrating traces.json → traces.db ...")
        try:
            with open(self.json_path, "r") as f:
                data = json.load(f)
            default = data.get("default_trace")
            with self.conn:
                for name, trace in data.get("traces", {}).items():
                    color = trace.get("color", self._random_color())
                    is_default = 1 if name == default else 0
                    self.conn.execute(
                        "INSERT INTO traces(name, color, is_default) VALUES (?, ?, ?)",
                        (name, color, is_default),
                    )
                    for frame_key, pts in trace.get("frames", {}).items():
                        frame = int(frame_key)
                        self.conn.executemany(
                            "INSERT INTO points(trace_name, frame, x, y) VALUES (?, ?, ?, ?)",
                            [(name, frame, p["x"], p["y"]) for p in pts],
                        )
            # Переименовываем json чтобы не мигрировать повторно
            os.rename(self.json_path, self.json_path + ".bak")
            logger.info("Migration complete. traces.json renamed to traces.json.bak")
        except Exception as e:
            logger.error("Migration failed: %s", e)

    # ----- Работа с трассами -----

    def trace_names(self) -> List[str]:
        rows = self.conn.execute("SELECT name FROM traces ORDER BY rowid").fetchall()
        return [r[0] for r in rows]

    def create_trace(self, name: str, color: Optional[str] = None) -> dict:
        if not name:
            raise ValueError("Trace name cannot be empty")
        if color is None:
            color = self._random_color()
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO traces(name, color, is_default) VALUES (?, ?, 0)",
                    (name, color),
                )
        except sqlite3.IntegrityError:
            raise ValueError(f"Trace '{name}' already exists")
        logger.info("Created trace '%s'", name)
        return {"color": color, "frames": {}}

    def rename_trace(self, old_name: str, new_name: str) -> dict:
        if not self._trace_exists(old_name):
            raise KeyError(f"Trace '{old_name}' not found")
        if self._trace_exists(new_name):
            raise ValueError(f"Trace '{new_name}' already exists")
        with self.conn:
            self.conn.execute(
                "UPDATE traces SET name=? WHERE name=?", (new_name, old_name)
            )
        return {"color": self.get_trace_color(new_name)}

    def delete_trace(self, name: str):
        if not self._trace_exists(name):
            raise KeyError(f"Trace '{name}' not found")
        with self.conn:
            self.conn.execute("DELETE FROM traces WHERE name=?", (name,))
        # Если удалили дефолтный — назначаем следующий
        remaining = self.trace_names()
        if remaining:
            self.conn.execute(
                "UPDATE traces SET is_default=1 WHERE name=?", (remaining[0],)
            )
            self.conn.commit()
        logger.info("Deleted trace '%s'", name)

    def get_default_trace(self) -> Optional[str]:
        row = self.conn.execute("SELECT name FROM traces WHERE is_default=1").fetchone()
        if row:
            return row[0]
        # Fallback — первый в списке
        names = self.trace_names()
        return names[0] if names else None

    def set_default_trace(self, name: str):
        if not self._trace_exists(name):
            raise KeyError(f"Trace '{name}' not found")
        with self.conn:
            self.conn.execute("UPDATE traces SET is_default=0")
            self.conn.execute("UPDATE traces SET is_default=1 WHERE name=?", (name,))

    def recolor_trace(self, name: str, color: str):
        if not self._trace_exists(name):
            raise KeyError(f"Trace '{name}' not found")
        with self.conn:
            self.conn.execute("UPDATE traces SET color=? WHERE name=?", (color, name))

    def get_trace_color(self, name: str) -> str:
        row = self.conn.execute(
            "SELECT color FROM traces WHERE name=?", (name,)
        ).fetchone()
        if not row:
            raise KeyError(f"Trace '{name}' not found")
        return row[0]

    # ----- Работа с точками -----

    def get_points(self, trace_name: str, frame_number: int) -> List[dict]:
        rows = self.conn.execute(
            "SELECT x, y FROM points WHERE trace_name=? AND frame=? ORDER BY id",
            (trace_name, frame_number),
        ).fetchall()
        return [{"x": r[0], "y": r[1]} for r in rows]

    def set_points(self, trace_name: str, frame_number: int, points: List[dict]):
        """Заменяет все точки кадра целиком."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM points WHERE trace_name=? AND frame=?",
                (trace_name, frame_number),
            )
            if points:
                self.conn.executemany(
                    "INSERT INTO points(trace_name, frame, x, y) VALUES (?, ?, ?, ?)",
                    [(trace_name, frame_number, p["x"], p["y"]) for p in points],
                )

    def add_point(
        self, trace_name: str, frame_number: int, x: float, y: float
    ) -> List[dict]:
        with self.conn:
            self.conn.execute(
                "INSERT INTO points(trace_name, frame, x, y) VALUES (?, ?, ?, ?)",
                (trace_name, frame_number, x, y),
            )
        return self.get_points(trace_name, frame_number)

    def clear_frame(self, trace_name: str, frame_number: int):
        with self.conn:
            self.conn.execute(
                "DELETE FROM points WHERE trace_name=? AND frame=?",
                (trace_name, frame_number),
            )

    def clear_trace(self, trace_name: str):
        with self.conn:
            self.conn.execute("DELETE FROM points WHERE trace_name=?", (trace_name,))

    def get_all_points(self) -> List[dict]:
        """Возвращает все точки всех трасс — для экспорта."""

        rows = self.conn.execute("""SELECT trace_name, frame, x, y
           FROM points
           ORDER BY trace_name, frame, id""").fetchall()
        return [{"trace": r[0], "frame": r[1], "x": r[2], "y": r[3]} for r in rows]

    # ----- Утилиты -----

    def _trace_exists(self, name: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM traces WHERE name=?", (name,)).fetchone()
        return row is not None

    def _random_color(self) -> str:
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    # Для совместимости с кодом который обращается к data["traces"]
    @property
    def colors(self) -> Dict[str, str]:
        rows = self.conn.execute("SELECT name, color FROM traces").fetchall()
        return {r[0]: r[1] for r in rows}

    def __del__(self):
        try:
            self.conn.close()
        except Exception:
            pass
