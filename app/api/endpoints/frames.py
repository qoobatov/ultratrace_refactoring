import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/frames", tags=["frames"])


@router.get("/times")
async def get_frame_times(study: StudySession = Depends(get_study_session)):
    """Возвращает список временных меток всех кадров (в секундах)."""
    times = study.get_frame_times()
    if not times:
        raise HTTPException(status_code=404, detail="No frame times available")
    return {"times": times, "count": len(times)}


@router.get("/{index}")
async def get_frame(index: int, study: StudySession = Depends(get_study_session)):
    try:
        img = study.get_frame(index)
        buf = io.BytesIO()
        # Меняем PNG на JPEG с качеством 85%
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/jpeg")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
