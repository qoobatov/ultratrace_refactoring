from fastapi import APIRouter, Depends, HTTPException, Body
from app.api.deps import get_study_session
from app.core.study import StudySession
from pydantic import BaseModel, Field

router = APIRouter(prefix="/contours", tags=["contours"])


class Point(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class TraceData(BaseModel):
    name: str
    color: str | None = None


class TraceRename(BaseModel):
    old_name: str
    new_name: str


class PointsPayload(BaseModel):
    points: list[Point]


@router.get("/traces")
async def list_traces(study: StudySession = Depends(get_study_session)):
    """List of all traces."""
    names = study.get_trace_names()
    default = study.get_default_trace()
    return {"traces": names, "default": default}


@router.post("/traces")
async def create_trace(
    body: TraceData, study: StudySession = Depends(get_study_session)
):
    """Create a new trace."""
    try:
        trace = study.create_trace(body.name, body.color)
        return trace
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/traces/{name}")
async def delete_trace(name: str, study: StudySession = Depends(get_study_session)):
    try:
        study.delete_trace(name)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")


@router.put("/traces/rename")
async def rename_trace(
    body: TraceRename, study: StudySession = Depends(get_study_session)
):
    try:
        study.rename_trace(body.old_name, body.new_name)
        return {"status": "ok"}
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/traces/{name}/color")
async def set_color(
    name: str, color: str = Body(...), study: StudySession = Depends(get_study_session)
):
    try:
        study.recolor_trace(name, color)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")


@router.get("/traces/{trace_name}/frames/{frame_number}")
async def get_points(
    trace_name: str, frame_number: int, study: StudySession = Depends(get_study_session)
):
    points = study.get_trace_points(trace_name, frame_number)
    return {"points": points}


@router.put("/traces/{trace_name}/frames/{frame_number}")
async def save_points(
    trace_name: str,
    frame_number: int,
    payload: PointsPayload,
    study: StudySession = Depends(get_study_session),
):
    try:
        points = [p.dict() for p in payload.points]
        study.save_trace_points(trace_name, frame_number, points)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")


@router.delete("/traces/{trace_name}/frames/{frame_number}")
async def clear_frame(
    trace_name: str, frame_number: int, study: StudySession = Depends(get_study_session)
):
    try:
        study.clear_trace_points(trace_name, frame_number)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")
