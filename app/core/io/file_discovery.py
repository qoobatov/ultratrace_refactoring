"""
Traverses the project directory and groups files by base names.
Does not use tkinter or magic, only os and standard extensions.
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Отображение расширений в наши ключи (как в оригинале)
EXTENSION_MAP = {
    ".dicom": ".dicom",
    ".ult": ".ult",
    ".wav": ".wav",
    ".flac": ".flac",
    ".ogg": ".ogg",
    ".mp3": ".mp3",
    ".TextGrid": ".TextGrid",
    ".txt": ".txt",  # может быть US.txt или просто .txt
    ".param": ".param",
}

# Дополнительные ключи для особых файлов
US_TXT_SUFFIX = "US.txt"
TRACK_SUFFIXES = ["_Track0", "_Track1", "_Track2"]


def discover_study_files(root_path: str) -> List[Dict]:
    """
    Возвращает список словарей, каждый описывает один набор связанных файлов.
    Формат элемента:
    {
        'name': str,           # базовое имя
        'extensions': {        # словарь расширение -> относительный путь
            '.dicom': 'subdir/file.dicom',
            '.wav': 'subdir/file.wav',
            ...
        },
        'audio_relpath': str|None,  # относительный путь к папке с аудио (если отличается)
        'processed': dict|None,     # {номер_кадра: путь} для заранее извлечённых PNG
    }
    """
    root_path = os.path.abspath(root_path)
    files_dict: Dict[str, Dict] = {}  # базовое_имя -> накапливаем расширения

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Пропускаем .git
        if ".git" in dirpath:
            continue
        for fname in filenames:
            if fname.startswith(".") or fname == "DS_Store":
                continue

            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_path)
            base, ext = os.path.splitext(fname)

            # Обработка специальных суффиксов аудио
            if ext == ".wav" and any(
                base.endswith(suffix) for suffix in TRACK_SUFFIXES
            ):
                for suffix in TRACK_SUFFIXES:
                    if base.endswith(suffix):
                        base = base[: -len(suffix)]
                        break
                # Track0 – основной аудио, Track1/2 – пропускаем, но сохраняем audio_relpath
                if base.endswith("_Track0"):
                    base = base[:-7]  # убрать _Track0
                    audio_relpath = os.path.dirname(rel_path)
                else:
                    continue  # не добавляем Track1/2
            else:
                audio_relpath = None

            # Особый случай: US.txt – объединяем с базой без US
            if ext == ".txt" and base.endswith("US"):
                base = base[:-2]  # убрать 'US'
                ext_key = US_TXT_SUFFIX
            else:
                ext_key = ext

            # Игнорируем неизвестные расширения
            if ext_key not in EXTENSION_MAP and ext != ".png":
                continue

            # Уникальное базовое имя с учётом подпапки (как в оригинале: subdir/basename)
            rel_dir = os.path.relpath(dirpath, root_path)
            if rel_dir == ".":
                full_base = base
            else:
                full_base = os.path.join(rel_dir, base).replace(os.sep, "/")

            if full_base not in files_dict:
                files_dict[full_base] = {
                    "name": full_base,
                    "extensions": {},
                    "audio_relpath": None,
                    "processed": None,
                }

            entry = files_dict[full_base]

            # Сохраняем расширение
            if ext_key not in entry["extensions"]:
                entry["extensions"][ext_key] = rel_path

            if audio_relpath:
                entry["audio_relpath"] = audio_relpath

            # Препроцессированные PNG (папка *_dicom_to_png)
            if ext == ".png" and "_dicom_to_png" in dirpath:
                # Имя файла вида: basename_frame_0001.png
                parts = base.split("_frame_")
                if len(parts) == 2:
                    frame_num = parts[1]
                    if entry["processed"] is None:
                        entry["processed"] = {}
                    entry["processed"][str(int(frame_num))] = rel_path

    # Сортируем по имени для детерминированного порядка
    sorted_names = sorted(files_dict.keys())
    result = [files_dict[name] for name in sorted_names]
    logger.info(f"Discovered {len(result)} file sets in {root_path}")
    return result
