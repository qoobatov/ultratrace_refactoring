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

    # Извлекаем нужный участок с запасом для окна
    duration = end_time - start_time
    extra = window_length  # приблизительно
    t_start = max(0, start_time - extra)
    t_end = min(len(data) / samplerate, end_time + extra)
    start_sample = int(t_start * samplerate)
    end_sample = int(t_end * samplerate)
    segment = data[start_sample:end_sample]

    # Вычисляем спектрограмму
    nperseg = int(window_length * samplerate)
    if nperseg < 1:
        nperseg = 1
    f, t, Sxx = scipy_spectrogram(
        segment, fs=samplerate, nperseg=nperseg, noverlap=nperseg // 2
    )

    # Обрезаем по частоте
    freq_mask = f <= freq_max
    Sxx = Sxx[freq_mask, :]
    f = f[freq_mask]

    # Переводим в dB, нормируем и инвертируем для отображения (как в оригинале)
    Sxx_db = 10 * np.log10(Sxx + 1e-10)  # маленькая константа для избежания log(0)
    mx = Sxx_db.max()
    Sxx_db = Sxx_db.clip(mx - dynamic_range, mx) - mx
    Sxx_db = Sxx_db * (-255.0 / dynamic_range)
    Sxx_db = Sxx_db.astype(np.uint8)

    # Масштабируем до заданных размеров
    zoom_y = height / Sxx_db.shape[0]
    zoom_x = width / Sxx_db.shape[1]
    img = zoom(
        Sxx_db, (zoom_y, zoom_x), order=0
    )  # nearest neighbor для сохранения дискретности
    img = np.clip(img, 0, 255).astype(np.uint8)

    # Превращаем в RGB (оттенки серого)
    img_rgb = np.stack([img, img, img], axis=2)

    return img_rgb
