"""
Генератор спектрограммы с использованием scipy.
Не зависит от GUI и parselmouth.
"""

import numpy as np
from scipy.signal import spectrogram as scipy_spectrogram
from scipy.ndimage import zoom
import logging

logger = logging.getLogger(__name__)


def generate_spectrogram_image(
    audio_path: str,
    start_time: float,
    end_time: float,
    width: int = 800,
    height: int = 106,
    freq_max: float = 5000,
    window_length: float = 0.005,
    dynamic_range: float = 90,
) -> np.ndarray:
    """
    Возвращает RGB-изображение спектрограммы как numpy-массив.
    Параметры соответствуют оригинальному UltraTrace.
    """
    try:
        import soundfile as sf
    except ImportError:
        raise ImportError("soundfile is required for spectrogram generation")

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
        return np.zeros((height, width, 3), dtype=np.uint8)

    # Обрезаем по времени — убираем запас extra
    total_dur = t_end - t_start
    t_rel_start = (start_time - t_start) / total_dur
    t_rel_end = (end_time - t_start) / total_dur
    col_start = int(t_rel_start * Sxx.shape[1])
    col_end = int(t_rel_end * Sxx.shape[1])
    col_start = max(0, col_start)
    col_end = min(Sxx.shape[1], col_end)
    if col_end > col_start:
        Sxx = Sxx[:, col_start:col_end]

    # dB нормировка
    Sxx_db = 10 * np.log10(Sxx + 1e-10)
    mx = Sxx_db.max()
    Sxx_db = Sxx_db.clip(mx - dynamic_range, mx) - mx
    Sxx_db = Sxx_db * (-255.0 / dynamic_range)
    Sxx_db = np.clip(Sxx_db, 0, 255).astype(np.uint8)

    # Масштабируем с билинейной интерполяцией
    zoom_y = height / Sxx_db.shape[0]
    zoom_x = width / Sxx_db.shape[1]
    img = zoom(Sxx_db, (zoom_y, zoom_x), order=1)
    img = np.clip(img, 0, 255).astype(np.uint8)

    img_rgb = np.stack([img, img, img], axis=2)
    return img_rgb
