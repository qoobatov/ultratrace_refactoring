"""
Traverses the project directory and groups files by base names.
Does not use tkinter or magic, only os and standard extensions.

Also owns metadata.json — the primary, human-readable index of a study
directory. It points to traces.json (see issue #3: metadata.json is
primary and references the traces file, not the other way around).
ContourManager only reads this reference; it never writes metadata.json.
"""

import json
import os
import time
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

METADATA_FILENAME = "metadata.json"
DEFAULT_TRACES_FILENAME = "traces.json"


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


# ---------------------------------------------------------------------------
# metadata.json — primary index of the study directory (issue #3).
#
# metadata.json is the single source of truth for "what files exist in this
# directory" and "where is the traces file". It is generated fresh on an
# empty directory the same way it is regenerated on rescan — one code path
# for both, so the two never drift apart. ContourManager reads traces_file
# from here but never writes to this file itself.
# ---------------------------------------------------------------------------


def _metadata_path(root_path: str) -> str:
    return os.path.join(root_path, METADATA_FILENAME)


def _atomic_write_json(path: str, data: dict):
    """Пишет во временный файл и атомарно заменяет — не оставит битый
    metadata.json, если процесс упадёт посреди записи."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def load_metadata(root_path: str) -> Optional[dict]:
    """Читает metadata.json как есть, без обхода директории. Возвращает
    None, если файла нет или он повреждён."""
    path = _metadata_path(root_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read metadata.json: %s", e)
        return None


def save_metadata(
    root_path: str, file_sets: List[Dict], traces_file: Optional[str] = None
) -> dict:
    """
       Перезаписывает metadata.json. Сохраняет уже существующую ссылку на
       traces_file, если она была и явно не переопределена — metadata.json
       указывает на traces.json, а не наоборот, так что эта ссылка не должна
       теряться при пересканировании.

    Если ссылка потеряна (поле отсутствует и в существующем metadata.json,
    и не передана явно), пробуем обнаружить traces.json на диске по
    дефолтному имени, прежде чем создавать новый пустой — иначе рискуем
    молча "осиротить" файл с уже размеченными данными.
    """

    existing = load_metadata(root_path) or {}
    resolved_traces_file = traces_file or existing.get("traces_file")

    if not resolved_traces_file:
        if os.path.exists(os.path.join(root_path, DEFAULT_TRACES_FILENAME)):
            logger.info("Discovered existing traces.json during crawl")
        resolved_traces_file = DEFAULT_TRACES_FILENAME

    metadata = {
        "files": file_sets,
        "traces_file": resolved_traces_file,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _atomic_write_json(_metadata_path(root_path), metadata)
    logger.info(
        "Wrote metadata.json for %s (%d file sets, traces_file=%s)",
        root_path,
        len(file_sets),
        resolved_traces_file,
    )
    return metadata


def load_or_generate_metadata(root_path: str, force_rescan: bool = False) -> dict:
    """
    Единая точка входа для получения состояния директории study.

    - Если metadata.json уже существует и force_rescan=False — читаем его
      как есть, без повторного обхода директории (быстрый путь при обычном
      старте StudySession).
    - Иначе (файла нет вообще, либо явно запрошен rescan) — обходим
      директорию заново через discover_study_files() и перезаписываем
      metadata.json, сохраняя существующую ссылку на traces_file.

    Пустая директория проходит тот же путь, что и rescan: файлов не найдено,
    но metadata.json всё равно генерируется свежим, с "files": [].
    """
    if not force_rescan:
        existing = load_metadata(root_path)
        if existing is not None:
            return existing

    file_sets = discover_study_files(root_path)
    return save_metadata(root_path, file_sets)
