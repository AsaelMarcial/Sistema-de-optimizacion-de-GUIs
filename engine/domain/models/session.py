import uuid
from pathlib import Path
import shutil
from typing import List, TypedDict
from werkzeug.datastructures import FileStorage

from engine.adapters.file_system.file_manager import is_corrupted

# Define the strict internal structure of your dictionary for the type checker
class AreaStructure(TypedDict):
    rootPath: Path
    paths: List[Path]


class Session:
    SESSIONS_ROOT: Path = Path(__file__).resolve().parents[3] / "workspace" / "sessions"
    TEXT_FILE_SUFFIXES = {".html", ".css", ".js", ".svg"}
    VIDEO_FILE_SUFFIXES = {".mp4", ".m4v", ".mov", ".webm", ".ogv"}

    def __init__(self) -> None:
        self.session_id: str = uuid.uuid4().hex
        self.session_dir: Path = (self.SESSIONS_ROOT / f"session_{self.session_id}").resolve()

        # Explicitly type each dictionary using the AreaStructure template
        self._before: AreaStructure = {
            "rootPath": self.session_dir / "before",
            "paths": []
        }
        self._after: AreaStructure = {
            "rootPath": self.session_dir / "after",
            "paths": []
        }
        self._artifacts: AreaStructure = {
            "rootPath": self.session_dir / "artifacts",
            "paths": []
        }
        self.file_types: dict[Path, str] = {}
        self._register_fixed_artifacts()

    def _register_fixed_artifacts(self) -> None:
        for filename in ("before.png", "after.png", "palette_preview.png"):
            self.save_in_artifacts(self.get_area_root("artifacts") / filename)

    def get_area_root(self, area: str) -> Path:
        """
        Calculates and returns the physical root path for a given area using
        structural pattern matching.
        """
        match area.strip().lower():
            case "before":
                return self._before["rootPath"]
            case "after":
                return self._after["rootPath"]
            case "artifacts":
                return self._artifacts["rootPath"]
            case _:
                raise ValueError(
                    f"Invalid area: '{area}'. Choose 'before', 'after', or 'artifacts'."
                )

    # --- Mutator Methods ---

    def save_in_before(self, path: Path) -> None:
        resolved_path = Path(path).resolve()
        if resolved_path not in self._before["paths"]:
            self._before["paths"].append(resolved_path)

    def save_in_after(self, path: Path) -> None:
        resolved_path = Path(path).resolve()
        if resolved_path not in self._after["paths"]:
            self._after["paths"].append(resolved_path)

    def save_in_artifacts(self, path: Path) -> None:
        resolved_path = Path(path).resolve()
        if resolved_path not in self._artifacts["paths"]:
            self._artifacts["paths"].append(resolved_path)

    def update_area_root_paths(self, area: str) -> List[Path]:
        root = self.get_area_root(area)
        paths: list[Path] = []
        if root.is_dir():
            for dirpath, _dirnames, filenames in root.walk():
                for filename in filenames:
                    paths.append((dirpath / filename).resolve())
            paths.sort()

        match area.strip().lower():
            case "before":
                self._before["paths"] = paths
            case "after":
                self._after["paths"] = paths
            case "artifacts":
                self._artifacts["paths"] = paths
            case _:
                raise ValueError(
                    f"Invalid area: '{area}'. Choose 'before', 'after', or 'artifacts'."
                )

        return paths

    def parallel_path(self, path: Path, from_area: str, to_area: str) -> Path:
        source_root = self.get_area_root(from_area).resolve()
        target_root = self.get_area_root(to_area).resolve()
        relative_path = Path(path).resolve().relative_to(source_root)
        return (target_root / relative_path).resolve()

    def copy_area_files(self, from_area: str, to_area: str) -> list[Path]:
        source_root = self.get_area_root(from_area).resolve()
        target_root = self.get_area_root(to_area).resolve()
        if not source_root.is_dir():
            return []

        shutil.copytree(source_root, target_root, dirs_exist_ok=True)
        self.update_area_root_paths(to_area)
        return self.update_area_root_paths(to_area)

    def validate_materialized_project(
        self,
        area: str,
        analyzed_files: list[tuple[FileStorage, Path, str]],
    ) -> bool:
        root = self.get_area_root(area).resolve()
        files = tuple(self.update_area_root_paths(area))

        if not files:
            raise ValueError("El proyecto materializado no contiene archivos.")

        if len(files) != len(analyzed_files):
            raise ValueError(
                "El proyecto materializado no coincide con los archivos analizados."
            )

        self.file_types = {}
        matched_indexes: set[int] = set()
        for path in files:
            if not path.exists():
                raise ValueError(f"No existe el archivo: {path}")

            for index, (analyzed_file, analyzed_path, analyzed_type) in enumerate(analyzed_files):
                if index in matched_indexes:
                    continue

                try:
                    if not path.samefile((root / analyzed_path).resolve()):
                        continue
                except OSError:
                    continue

                matched_indexes.add(index)
                self.file_types[path.resolve()] = analyzed_type

                validation_type = (
                    Path(analyzed_file.filename or "").suffix.lower()
                    if analyzed_type == "video"
                    and Path(analyzed_file.filename or "").suffix.lower() in {".jpg", ".jpeg"}
                    else analyzed_type
                )
                corrupted, message = is_corrupted(analyzed_file, validation_type)
                if corrupted:
                    raise ValueError(f"El archivo materializado no pudo abrirse: {path}: {message}")
                break
            else:
                raise ValueError(f"No se encontró metadata analizada para el archivo: {path}")

        return True

    # --- Query Methods ---

    def get_by_type(self, file_type: str) -> list[Path]:
        clean_type = str(file_type or "").strip().lower()
        if clean_type in self.VIDEO_FILE_SUFFIXES:
            clean_type = "video"
        extension_type = clean_type if clean_type.startswith(".") else f".{clean_type}"

        return sorted(
            path
            for path, stored_type in self.file_types.items()
            if (
                str(stored_type or "").strip().lower() in {clean_type, extension_type}
                or (
                    clean_type == "video"
                    and path.suffix.lower() in self.VIDEO_FILE_SUFFIXES
                )
            )
        )

    def find_by_suffix(self, area: str, suffix: str) -> list[Path]:
        """
        Filters and gathers Paths by their file extensions inside a specific area.
        Uses structural pattern matching to extract the target path list.
        """
        clean_suffix = suffix.lower().lstrip(".")
        search_pattern = f"*.{clean_suffix}"

        root = self.get_area_root(area)
        if not root.is_dir():
            return []

        return sorted(path.resolve() for path in root.rglob(search_pattern, case_sensitive=False) if path.is_file())

    def find_by_full_path(self, area: str, path: str | Path) -> Path | None:
        root = self.get_area_root(area).resolve()
        if not root.is_dir():
            return None

        normalized_path = Path(Path(path).as_posix()).resolve() if isinstance(path, str) else Path(path.as_posix()).resolve()

        relative_path = Path(*normalized_path.parts)

        direct_path = (
            normalized_path.resolve()
            if normalized_path.is_absolute()
            else (root / relative_path).resolve()
        )
        if direct_path.is_file() and direct_path.is_relative_to(root):
            return direct_path.relative_to(root, walk_up=True)

        matches = sorted(
            candidate.resolve()
            for candidate in root.rglob(
                f"{relative_path.stem}.*",
                case_sensitive=False,
            )
            if candidate.is_file() and candidate.name.casefold().startswith(relative_path.stem.casefold())
        )

        if relative_path.suffix:
            same_suffix = [
                candidate
                for candidate in self.find_by_suffix(area, str(relative_path.suffix))
                if candidate.name.casefold() == relative_path.name.casefold()
            ]
            if same_suffix:
                matches = same_suffix
            elif relative_path.suffix.lower() in self.VIDEO_FILE_SUFFIXES:
                matches = [
                    candidate
                    for candidate in self.get_by_type("video")
                    if candidate.stem.lower() == relative_path.stem.lower()
                ]

        if len(matches) == 1:
            return matches[0].relative_to(root, walk_up=True)

        for index in range(len(relative_path.parts)):
            partial_path = (root / Path(*relative_path.parts[index:])).resolve()
            for match in matches:
                try:
                    if partial_path.samefile(match):
                        return match.relative_to(root, walk_up=True)
                except OSError:
                    continue

        return None
    
    def get_path(self, name: str, area: str, suffix: str) -> Path:
        """
        Retrieves a single unique Path by its name, area, and suffix.
        All three parameters are strictly required. Uses structural pattern matching.
        """
        clean_name = name.strip()
        clean_relative_path = Path(clean_name.replace("\\", "/"))
        clean_suffix = suffix.lower() if suffix.startswith('.') else f".{suffix.lower()}"

        root = self.get_area_root(area)
        if len(clean_relative_path.parts) > 1:
            direct_path = (root / clean_relative_path).resolve()
            if direct_path.suffix.lower() == clean_suffix:
                return direct_path
            raise FileNotFoundError(
                f"Path '{clean_name}' with suffix '{clean_suffix}' "
                f"was not found in area '{area}'."
            )

        search_name = clean_name if clean_relative_path.suffix else f"{clean_name}{clean_suffix}"
        matches = (
            sorted(
                path.resolve()
                for path in root.rglob(search_name)
                if path.is_file() and path.suffix.lower() == clean_suffix
            )
            if root.is_dir()
            else []
        )

        if not matches:
            direct_path = (root / search_name).resolve()
            if direct_path.suffix.lower() == clean_suffix:
                return direct_path
            raise FileNotFoundError(
                f"Path '{clean_name}' with suffix '{clean_suffix}' "
                f"was not found in area '{area}'."
            )

        if len(matches) > 1:
            raise ValueError(
                f"Ambiguity detected: Multiple paths match '{clean_name}' "
                f"with suffix '{clean_suffix}' in area '{area}'."
            )

        return matches[0]
