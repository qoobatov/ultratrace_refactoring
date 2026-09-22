"""
Traverses the project directory and groups files by base names.
Does not use tkinter or magic, only os and standard extensions.

Also owns ultratrace_metadata.json — the primary, human-readable index of
a study directory. It points to traces.json (see issue #3: metadata is
primary and references the traces file, not the other way around).
ContourManager only reads this reference; it never writes this file.

The filename is deliberately namespaced (not a generic "metadata.json")
because users may point UltraTrace at a broad directory that happens to
contain an unrelated project with its own metadata.json (e.g. a static
site generator's build output) — a generic name risks silently reading
someone else's file and crashing deep inside StudySession.
"""

import json
import os
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Отображение расширений в наши ключи (как в оригинале).
# US.txt маппится в ".txt" — см. комментарий рядом.
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

# Папки, которые не имеют отношения к study-данным, но часто лежат рядом
# (venv, кэши IDE, node_modules). Спускаться в них бессмысленно и опасно:
# именно так в индекс попадали .png из .cache/JetBrains/... и ломали
# StudySession через "Unsupported file set".
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

METADATA_FILENAME = "ultratrace_metadata.json"
DEFAULT_TRACES_FILENAME = "traces.json"


def discover_study_files(root_path: str) -> List[Dict]:
    """
    Возвращает список словарей, каждый описывает один набор связанных файлов.
    Формат элемента:
    {
        'name': str,           # базовое имя (subdir/basename)
        'extensions': {        # словарь расширение -> относительный путь
            '.dicom': 'subdir/file.dicom',
            '.wav': 'subdir/file.wav',
            ...
        },
        'audio_relpath': str|None,  # относительный путь к папке с аудио
        'processed': dict|None,     # {номер_кадра: путь} для PNG из *_dicom_to_png
    }

    Записи без единого исходного файла (пустой extensions) на выходе
    отбрасываются: StudySession всё равно не сможет с ними работать.
    """
    root_path = os.path.abspath(root_path)
    files_dict: Dict[str, Dict] = {}  # базовое_имя -> накапливаем расширения

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Мутируем dirnames in-place — так os.walk не будет спускаться
        # в пропущенные подпапки (в отличие от простого "continue").
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            if fname.startswith(".") or fname == "DS_Store":
                continue

            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_path)
            base, ext = os.path.splitext(fname)

            audio_relpath: Optional[str] = None

            # --- Аудио-треки: base_Track0/1/2.wav ---
            if ext == ".wav" and any(base.endswith(s) for s in TRACK_SUFFIXES):
                matched = next(s for s in TRACK_SUFFIXES if base.endswith(s))
                base = base[: -len(matched)]
                if matched != "_Track0":
                    # Track1/Track2 — дубли основного канала, пропускаем
                    continue
                audio_relpath = os.path.dirname(rel_path)

            # --- US.txt: маппится в ".txt", база без суффикса US ---
            if ext == ".txt" and base.endswith("US"):
                base = base[:-2]
                ext_key = ".txt"
            else:
                ext_key = ext

            # Препроцессированные PNG (папка *_dicom_to_png)
            is_processed_png = ext == ".png" and "_dicom_to_png" in dirpath

            if ext_key not in EXTENSION_MAP and not is_processed_png:
                continue

            # Уникальное базовое имя с учётом подпапки: subdir/basename
            rel_dir = os.path.relpath(dirpath, root_path)
            if rel_dir == ".":
                full_base = base
            else:
                full_base = os.path.join(rel_dir, base).replace(os.sep, "/")

            entry = files_dict.setdefault(
                full_base,
                {
                    "name": full_base,
                    "extensions": {},
                    "audio_relpath": None,
                    "processed": None,
                },
            )

            if is_processed_png:
                # Имя файла вида: basename_frame_0001.png
                parts = base.split("_frame_")
                if len(parts) != 2:
                    continue
                try:
                    frame_num = int(parts[1])
                except ValueError:
                    logger.debug("Skipping malformed frame filename: %s", rel_path)
                    continue
                if entry["processed"] is None:
                    entry["processed"] = {}
                entry["processed"][str(frame_num)] = rel_path
            else:
                if ext_key not in entry["extensions"]:
                    entry["extensions"][ext_key] = rel_path
                elif entry["extensions"][ext_key] != rel_path:
                    # Например, fooUS.txt и foo.txt с одинаковой базой —
                    # сохраняем первый, о втором предупреждаем.
                    logger.warning(
                        "Duplicate extension %s for base %s: keeping %s, ignoring %s",
                        ext_key,
                        full_base,
                        entry["extensions"][ext_key],
                        rel_path,
                    )
                if audio_relpath:
                    entry["audio_relpath"] = audio_relpath

    # Отбрасываем записи без исходных файлов (например, только PNG
    # без соответствующего .dicom, или пустые наборы).
    filtered = {k: v for k, v in files_dict.items() if v["extensions"]}

    sorted_names = sorted(filtered.keys())
    result = [filtered[name] for name in sorted_names]
    logger.info(
        "Discovered %d file sets in %s (dropped %d empty)",
        len(result),
        root_path,
        len(files_dict) - len(result),
    )
    return result


# ---------------------------------------------------------------------------
# ultratrace_metadata.json — primary index of the study directory (issue #3).
#
# It is the single source of truth for "what files exist in this directory"
# and "where is the traces file". It is generated fresh on an empty
# directory the same way it is regenerated on rescan — one code path for
# both, so the two never drift apart. ContourManager reads traces_file from
# here but never writes to this file itself.
# ---------------------------------------------------------------------------


def _metadata_path(root_path: str) -> str:
    return os.path.join(root_path, METADATA_FILENAME)


def _atomic_write_json(path: str, data: dict):
    """Пишет во временный файл и атомарно заменяет — не оставит битый
    metadata-файл, если процесс упадёт посреди записи."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def load_metadata(root_path: str) -> Optional[dict]:
    """Читает ultratrace_metadata.json как есть, без обхода директории.
    Возвращает None, если файла нет или он повреждён."""
    path = _metadata_path(root_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read %s: %s", METADATA_FILENAME, e)
        return None


def _is_valid_metadata(metadata: dict) -> bool:
    """
    Проверяет структуру существующего metadata-файла перед тем, как ему
    довериться. Защита от устаревших/повреждённых/сторонних файлов (даже
    после переименования в ultratrace_metadata.json остаётся полезной —
    например, против файлов от старых версий UltraTrace) — лучше молча
    пересканировать директорию заново, чем упасть с KeyError глубоко
    внутри StudySession.
    """
    if not isinstance(metadata, dict):
        return False
    files = metadata.get("files")
    if not isinstance(files, list):
        return False
    for f in files:
        if not isinstance(f, dict):
            return False
        if "name" not in f or "extensions" not in f:
            return False
        # extensions должен быть словарём — старые плоские схемы
        # ({'.txt': path, ...} в корне) здесь и отсеиваются.
        if not isinstance(f["extensions"], dict):
            return False
    return True


def save_metadata(
    root_path: str, file_sets: List[Dict], traces_file: Optional[str] = None
) -> dict:
    """
    Перезаписывает ultratrace_metadata.json. Сохраняет уже существующую
    ссылку на traces_file, если она была и явно не переопределена —
    metadata.json указывает на traces.json, а не наоборот, так что эта
    ссылка не должна теряться при пересканировании.

    Если ссылка потеряна (поле отсутствует и в существующем файле, и не
    передана явно), пробуем обнаружить traces.json на диске по дефолтному
    имени, прежде чем создавать новый пустой — иначе рискуем молча
    "осиротить" файл с уже размеченными данными.
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
        "Wrote %s for %s (%d file sets, traces_file=%s)",
        METADATA_FILENAME,
        root_path,
        len(file_sets),
        resolved_traces_file,
    )
    return metadata


def load_or_generate_metadata(root_path: str, force_rescan: bool = False) -> dict:
    """
    Единая точка входа для получения состояния директории study.

    - Если ultratrace_metadata.json уже существует, имеет ожидаемую
      структуру и force_rescan=False — читаем его как есть, без повторного
      обхода директории (быстрый путь при обычном старте StudySession).
    - Иначе (файла нет, он повреждён/невалидной структуры, либо явно
      запрошен rescan) — обходим директорию заново через
      discover_study_files() и перезаписываем metadata-файл, сохраняя
      существующую ссылку на traces_file.

    Пустая директория проходит тот же путь, что и rescan: файлов не найдено,
    но metadata-файл всё равно генерируется свежим, с "files": [].
    """
    if not force_rescan:
        existing = load_metadata(root_path)
        if existing is not None and _is_valid_metadata(existing):
            return existing
        if existing is not None:
            logger.warning(
                "%s in %s has an unexpected structure — rescanning directory",
                METADATA_FILENAME,
                root_path,
            )

    file_sets = discover_study_files(root_path)
    return save_metadata(root_path, file_sets)
