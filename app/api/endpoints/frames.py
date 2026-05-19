import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/frames", tags=["frames"])


@router.get("/{index}")
async def get_frame(index: int, study: StudySession = Depends(get_study_session)):
    try:
        img = study.get_frame(index)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
