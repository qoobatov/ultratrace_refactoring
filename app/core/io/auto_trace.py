import numpy as np
from PIL import Image


def auto_trace(
    image: Image.Image,
    n_columns: int = 30,
    x_start: float = 0.15,
    x_end: float = 0.85,
    y_start: float = 0.15,
    y_end: float = 0.85,
) -> list[dict]:
    gray = np.array(image.convert("L"), dtype=np.float32)
    h, w = gray.shape

    from scipy.ndimage import gaussian_filter

    smoothed = gaussian_filter(gray, sigma=2.0)
    grad = np.diff(smoothed, axis=0)

    points = []

    px_start = int(w * x_start)
    px_end = int(w * x_end)
    col_width = (px_end - px_start) / n_columns

    search_start = int(h * y_start)
    search_end = int(h * y_end)

    # Порог яркости — пиксели темнее этого считаются фоном
    brightness_threshold = float(smoothed.max() * 0.3)

    for i in range(n_columns):
        col_start = px_start + int(i * col_width)
        col_end = px_start + int((i + 1) * col_width)
        col_x = (col_start + col_end) / 2

        col_grad = grad[:, col_start:col_end].mean(axis=1)
        col_brightness = smoothed[:, col_start:col_end].mean(axis=1)

        # Ищем сверху вниз первый пиксель где:
        # 1. градиент значимый
        # 2. яркость выше порога (не фон)
        found = None
        grad_threshold = np.abs(col_grad[search_start:search_end]).max() * 0.4

        for y in range(search_start, search_end):
            if (
                abs(col_grad[y]) > grad_threshold
                and col_brightness[y] > brightness_threshold
            ):
                found = y
                break

        if found is None:
            continue

        points.append(
            {
                "x": round(col_x / w, 4),
                "y": round(found / h, 4),
            }
        )

    return points
