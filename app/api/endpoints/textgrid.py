from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/textgrid", tags=["textgrid"])


class IntervalTextUpdate(BaseModel):
    text: str


@router.get("/intervals")
async def get_intervals(study: StudySession = Depends(get_study_session)):
    """Returns all intervals from the TextGrid."""
    return study.get_all_intervals()


@router.put("/intervals/{tier}/{idx}")
async def update_interval_text(
    tier: str,
    idx: int,
    payload: IntervalTextUpdate,
    study: StudySession = Depends(get_study_session),
):
    """Меняет текст интервала (mark) и сохраняет TextGrid на диск."""
    try:
        return study.update_interval_text(tier, idx, payload.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {e}")


@router.get("/backup-status")
async def get_backup_status(study: StudySession = Depends(get_study_session)):
    """Есть ли .bak-снимок TextGrid (для активации кнопки Revert)."""
    return {"hasBackup": study.has_textgrid_backup()}


@router.post("/revert")
async def revert_textgrid(study: StudySession = Depends(get_study_session)):
    """Восстанавливает TextGrid из .bak (отменяет все правки mark)."""
    try:
        return study.revert_textgrid_from_backup()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revert failed: {e}")


@router.get("/search")
async def search_textgrid(
    pattern: str = Query(..., description="Регулярное выражение"),
    context_size: int = Query(3, ge=0),
    study: StudySession = Depends(get_study_session),
):
    """Search intervals using a regular expression."""
    return study.search(pattern, context_size)
