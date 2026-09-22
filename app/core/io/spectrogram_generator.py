"""
Генератор спектрограммы с использованием scipy.
Не зависит от GUI и parselmouth.
"""

import numpy as np
from scipy.signal import spectrogram as scipy_spectrogram
from scipy.ndimage import zoom
import logging

logger = logging.getLogger(__name__)

SUPPORTED_COLORMAPS = ("grayscale", "thermal", "inferno", "viridis")


def _apply_colormap(img: np.ndarray, colormap: str) -> np.ndarray:
    """
    Применяет палитру к grayscale-изображению (uint8, 0..255).
    img: 0 — энергия, 255 — тишина.
    Возвращает RGB (height, width, 3) uint8.
    """
    if colormap == "grayscale":
        return np.stack([img, img, img], axis=2)

    # Для цветных палитр matplotlib: 1.0 — «горячо» (энергия), 0.0 — «холодно».
    # У нас наоборот, поэтому инвертируем: 1 - img/255.
    try:
        import matplotlib
    except ImportError as e:
        raise ImportError("matplotlib is required for colorized spectrograms") from e

    cmap_name = {
        "thermal": "hot",
        "inferno": "inferno",
        "viridis": "viridis",
    }.get(colormap, "gray")

    cmap = matplotlib.colormaps[cmap_name]
    inv = (255.0 - img.astype(np.float32)) / 255.0  # 0..1, 1 = энергия
    rgba = cmap(inv)  # (H, W, 4), float 0..1
    return (rgba[:, :, :3] * 255.0).astype(np.uint8)


def generate_spectrogram_image(
    audio_path: str,
    start_time: float,
    end_time: float,
    width: int = 800,
    height: int = 106,
    freq_max: float = 5000,
    window_length: float = 0.005,
    dynamic_range: float = 90,
    colormap: str = "grayscale",
    threshold: int = 0,
) -> np.ndarray:
    """
    Возвращает RGB-изображение спектрограммы как numpy-массив.
    Параметры соответствуют оригинальному UltraTrace.
    """
    try:
        import soundfile as sf
    except ImportError:
        raise ImportError("soundfile is required for spectrogram generation")

    if colormap not in SUPPORTED_COLORMAPS:
        colormap = "grayscale"
    threshold = int(max(0, min(255, threshold)))

    # Загружаем аудио
    data, samplerate = sf.read(audio_path, always_2d=True)
    if data.ndim > 1:
        data = data[:, 0]  # моно

    duration = end_time - start_time

    # Адаптируем window_length для коротких фрагментов
    if duration < 0.1:
        window_length = min(window_length, duration / 8)
    elif duration < 0.3:
        window_length = min(window_length, duration / 6)

    # Извлекаем нужный участок с запасом для окна
    extra = window_length * 2
    t_start = max(0, start_time - extra)
    t_end = min(len(data) / samplerate, end_time + extra)
    start_sample = int(t_start * samplerate)
    end_sample = int(t_end * samplerate)
    segment = data[start_sample:end_sample]

    # nperseg не может быть больше длины сегмента
    nperseg = int(window_length * samplerate)
    nperseg = max(4, min(nperseg, len(segment) // 2))

    # Адаптируем noverlap для коротких фрагментов
    if duration < 0.1:
        noverlap = int(nperseg * 0.95)
    elif duration < 0.3:
        noverlap = int(nperseg * 0.85)
    else:
        noverlap = int(nperseg * 0.75)

    # noverlap должен быть меньше nperseg
    noverlap = min(noverlap, nperseg - 1)

    f, t, Sxx = scipy_spectrogram(
        segment,
        fs=samplerate,
        nperseg=nperseg,
        noverlap=noverlap,
        window="hann",
    )

    # Обрезаем по частоте
    freq_mask = f <= freq_max
    Sxx = Sxx[freq_mask, :]

    if Sxx.size == 0:
        blank = np.zeros((height, width, 3), dtype=np.uint8)
        return blank

    # ── Согласование по времени ──────────────────────────────────────────
    # scipy.signal.spectrogram возвращает колонки, чьи ЦЕНТРЫ лежат в t[k],
    # которые не совпадают с границами [start_time, end_time]. Интерполируем
    # Sxx на равномерную сетку целевого окна, чтобы изображение пиксель-в-
    # пиксель соответствовало запрошенному [start_time, end_time].
    t_abs = t + t_start
    hop = nperseg - noverlap
    n_target = max(
        2,
        int(round((end_time - start_time) * samplerate / hop)) + 1,
    )
    t_target = np.linspace(start_time, end_time, n_target)

    Sxx_aligned = np.empty((Sxx.shape[0], n_target), dtype=Sxx.dtype)
    for i in range(Sxx.shape[0]):
        Sxx_aligned[i] = np.interp(t_target, t_abs, Sxx[i])
    Sxx = Sxx_aligned
    # ─────────────────────────────────────────────────────────────────────

    # dB нормировка
    Sxx_db = 10 * np.log10(Sxx + 1e-10)
    mx = Sxx_db.max()
    floor = np.percentile(Sxx_db, 1)

    effective_range = min(dynamic_range, mx - floor)
    if effective_range <= 0:
        effective_range = dynamic_range
    effective_range = max(effective_range, 1.0)

    Sxx_db = Sxx_db.clip(mx - effective_range, mx) - mx
    Sxx_db = Sxx_db * (-255.0 / effective_range)
    Sxx_db = np.clip(Sxx_db, 0, 255).astype(np.uint8)

    # Масштабируем с билинейной интерполяцией
    zoom_y = height / Sxx_db.shape[0]
    zoom_x = width / Sxx_db.shape[1]
    img = zoom(Sxx_db, (zoom_y, zoom_x), order=1)
    img = np.clip(img, 0, 255).astype(np.uint8)

    # ── Threshold (отсечение слабого сигнала в фон) ──────────────────────
    if threshold > 0:
        cutoff = 255 - threshold
        img = np.where(img > cutoff, np.uint8(255), img)
    # ─────────────────────────────────────────────────────────────────────

    # ── Colormap ─────────────────────────────────────────────────────────
    return _apply_colormap(img, colormap)
