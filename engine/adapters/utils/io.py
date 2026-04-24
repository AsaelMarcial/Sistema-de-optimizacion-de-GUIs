import os


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def save_text(path: str, content: str) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()
