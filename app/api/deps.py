import os
from app.core.study import StudySession

_study_instance = None
_study_path = None


def get_study_session() -> StudySession:
    global _study_instance, _study_path
    current_path = os.environ.get("ULTRA_TRACE_DATA", "data/sample_study")
    if _study_instance is None or _study_path != current_path:
        _study_instance = StudySession(current_path)
        _study_path = current_path
    return _study_instance
