from __future__ import annotations

import json
import os
from typing import Any

from engine.utils.serialization_utils import json_default_numpy_serializer


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def save_json(path: str, data: Any, *, indent: int = 2) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=indent, ensure_ascii=False, default=json_default_numpy_serializer)


def save_text(path: str, content: str) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()
