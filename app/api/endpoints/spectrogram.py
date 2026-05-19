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
    study: StudySession = Depends(get_study_session),
):
    """Возвращает PNG-изображение спектрограммы для видимого диапазона времени."""
    if not study.audio_reader or not study.audio_reader.loaded:
        raise HTTPException(status_code=404, detail="No audio loaded")

    # Determine the visible time range from the TextGrid
    if study.textgrid:
        start = study.textgrid.minTime
        end = study.textgrid.maxTime
    else:
        # Or use the full audio duration
        start = 0
        end = study.audio_reader.duration

    try:
        img_array = generate_spectrogram_image(
            study.audio_reader.filepath,
            start,
            end,
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
