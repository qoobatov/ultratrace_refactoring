from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_study_session
from app.core.study import StudySession

router = APIRouter(prefix="/study", tags=["study"])


@router.get("/files")
async def list_study_files(study: StudySession = Depends(get_study_session)):
    return study.list_files()


@router.post("/switch-file")
async def switch_study_file(
    index: int = Query(...), study: StudySession = Depends(get_study_session)
):
    try:
        study.switch_file(index)
        return {"status": "ok", "current": study.current_file_index}
    except IndexError:
        raise HTTPException(status_code=404, detail="File index not found")


@router.get("/methods")
async def get_available_methods(study: StudySession = Depends(get_study_session)):
    return study.available_methods()


@router.post("/change-method")
async def change_reading_method(
    method: str = Query(...), study: StudySession = Depends(get_study_session)
):
    try:
        study.change_method(method)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
