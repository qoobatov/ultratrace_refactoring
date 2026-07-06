import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from app.api.deps import get_study_session
from app.core.study import StudySession
from app.core.io.auto_trace import auto_trace
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


class ColorData(BaseModel):
    color: str


@router.get("/traces")
async def list_traces(study: StudySession = Depends(get_study_session)):
    """Список всех трасс с цветами."""
    names = study.get_trace_names()
    default = study.get_default_trace()
    colors = {}
    for name in names:
        try:
            colors[name] = study.contours.get_trace_color(name)
        except:
            colors[name] = "#ff0000"
    return {"traces": names, "default": default, "colors": colors}


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
    name: str, data: ColorData, study: StudySession = Depends(get_study_session)
):
    try:
        study.recolor_trace(name, data.color)
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


@router.put("/traces/{name}/set-default")
async def set_default_trace(
    name: str, study: StudySession = Depends(get_study_session)
):
    try:
        study.set_default_trace(name)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")


@router.delete("/traces/{trace_name}/frames")
async def clear_all_frames(
    trace_name: str, study: StudySession = Depends(get_study_session)
):
    """Очистить все кадры для трассы (сбросить все точки)."""
    try:
        study.clear_all_trace_points(trace_name)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")


@router.post("/traces/{trace_name}/frames/{frame_number}/auto-trace")
async def auto_trace_frame(
    trace_name: str,
    frame_number: int,
    study: StudySession = Depends(get_study_session),
):
    try:
        image = study.get_frame(frame_number)
        points = auto_trace(image)
        study.save_trace_points(trace_name, frame_number, points)
        return {"status": "ok", "points": points}
    except KeyError:
        raise HTTPException(status_code=404, detail="Trace not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_contours(study: StudySession = Depends(get_study_session)):
    """
    Экспортирует все аннотированные точки в CSV.
    Колонки: file, trace, frame, time, tier, interval_label, x, y
    """
    all_points = study.contours.get_all_points()
    if not all_points:
        raise HTTPException(status_code=404, detail="No annotated points found")

    frame_times = study.get_frame_times()
    intervals = study.get_all_intervals()

    def find_interval_labels(time: float) -> dict:
        result = {}
        for iv in intervals:
            if iv["start"] <= time < iv["end"]:
                result[iv["tier"]] = iv["text"]
        return result

    fname = study.current_file.get("name", "export")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["file", "trace", "frame", "time", "tier", "interval_label", "x", "y"]
    )

    for pt in all_points:
        frame = pt["frame"]
        time = frame_times[frame - 1] if 0 < frame <= len(frame_times) else ""
        tier_labels = find_interval_labels(time) if time != "" else {}

        if tier_labels:
            for tier, label in tier_labels.items():
                writer.writerow(
                    [fname, pt["trace"], frame, time, tier, label, pt["x"], pt["y"]]
                )
        else:
            writer.writerow([fname, pt["trace"], frame, time, "", "", pt["x"], pt["y"]])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contours_{fname}.csv"},
    )
