from fastapi import APIRouter, Depends, Query
from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/textgrid", tags=["textgrid"])


@router.get("/intervals")
async def get_intervals(study: StudySession = Depends(get_study_session)):
    """Returns all intervals from the TextGrid."""
    return study.get_all_intervals()


@router.get("/search")
async def search_textgrid(
    pattern: str = Query(..., description="Регулярное выражение"),
    context_size: int = Query(3, ge=0),
    study: StudySession = Depends(get_study_session),
):
    """Search intervals using a regular expression."""
    return study.search(pattern, context_size)
