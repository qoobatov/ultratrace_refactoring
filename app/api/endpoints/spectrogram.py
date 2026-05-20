import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from app.api.deps import get_study_session
from app.core.study import StudySession
from app.core.io.spectrogram_generator import generate_spectrogram_image
from PIL import Image

router = APIRouter(prefix="/spectrogram", tags=["spectrogram"])


@router.get("/")
async def get_spectrogram(
    width: int = Query(800, ge=1),
    height: int = Query(106, ge=1),
    freq_max: float = Query(5000, ge=0),
    window_length: float = Query(0.005, gt=0),
    dynamic_range: float = Query(90, ge=0),
    start_time: float = Query(None, description="Start time in seconds, defaults to 0"),
    end_time: float = Query(
        None, description="End time in seconds, defaults to audio duration"
    ),
    study: StudySession = Depends(get_study_session),
):
    """Возвращает PNG-изображение спектрограммы для указанного временного окна."""
    if not study.audio_reader or not study.audio_reader.loaded:
        raise HTTPException(status_code=404, detail="No audio loaded")

    # Определяем границы времени
    audio_duration = study.audio_reader.duration
    if start_time is None:
        start_time = 0.0
    if end_time is None:
        end_time = audio_duration

    # Корректируем границы
    start_time = max(0.0, start_time)
    end_time = min(end_time, audio_duration)
    if start_time >= end_time:
        raise HTTPException(
            status_code=400, detail="start_time must be less than end_time"
        )

    try:
        img_array = generate_spectrogram_image(
            study.audio_reader.filepath,
            start_time,
            end_time,
            width=width,
            height=height,
            freq_max=freq_max,
            window_length=window_length,
            dynamic_range=dynamic_range,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Spectrogram generation failed: {str(e)}"
        )

    img = Image.fromarray(img_array)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")
