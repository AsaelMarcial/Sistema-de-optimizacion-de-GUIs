import os
import uuid

from app.config import get_session_dir


def create_session() -> dict:
    session_id = str(uuid.uuid4())[:8]
    session_dir = get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    return {"session_id": session_id, "session_dir": session_dir}