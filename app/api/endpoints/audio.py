import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/info")
async def audio_info(study: StudySession = Depends(get_study_session)):
    """Returns audio duration and other metadata."""
    if not study.audio_reader:
        raise HTTPException(status_code=404, detail="No audio loaded")
    return {
        "duration": study.audio_reader.duration,
        "sample_rate": study.audio_reader.frame_rate,
        "channels": study.audio_reader.channels,
    }


@router.get("/file")
async def get_audio_file(study: StudySession = Depends(get_study_session)):
    """Serves the audio file for the browser (supports Range requests)."""
    path = study.get_audio_filepath()
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    # FileResponse автоматически обрабатывает Range
    return FileResponse(path, media_type="audio/wav", filename=os.path.basename(path))
