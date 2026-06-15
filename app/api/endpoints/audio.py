import io
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/info")
async def audio_info(study: StudySession = Depends(get_study_session)):
    if not study.audio_reader:
        raise HTTPException(status_code=404, detail="No audio loaded")
    return {
        "duration": study.audio_reader.duration,
        "sample_rate": study.audio_reader.frame_rate,
        "channels": study.audio_reader.channels,
    }


@router.get("/file")
async def get_audio_file(study: StudySession = Depends(get_study_session)):
    path = study.get_audio_filepath()
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    response = FileResponse(
        path,
        media_type="audio/wav",
        filename=os.path.basename(path),
    )
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@router.get("/segment")
async def get_audio_segment(
    start: float,
    end: float,
    study: StudySession = Depends(get_study_session),
):
    """Возвращает точный кусок аудио от start до end (в секундах)."""
    from pydub import AudioSegment

    path = study.get_audio_filepath()
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    audio = AudioSegment.from_file(path)
    start_ms = round(start * 1000)
    end_ms = round(end * 1000)
    segment = audio[start_ms:end_ms]

    buf = io.BytesIO()
    segment.export(buf, format="wav")
    buf.seek(0)

    response = StreamingResponse(buf, media_type="audio/wav")
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response
