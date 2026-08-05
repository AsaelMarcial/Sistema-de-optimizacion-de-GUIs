import uuid
from pathlib import Path
import shutil
from typing import List, TypedDict

from engine.validators.project_uploaded import is_readable


# Define the strict internal structure of your dictionary for the type checker
class AreaStructure(TypedDict):
    rootPath: Path
    paths: List[Path]


class Session:
    SESSIONS_ROOT: Path = Path(__file__).resolve().parents[3] / "workspace" / "sessions"
    TEXT_FILE_SUFFIXES = {".html", ".css", ".js", ".svg"}

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
        copied_paths: list[Path] = []
        for source_path in self.update_area_root_paths(from_area):
            target_path = self.parallel_path(source_path, from_area, to_area)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists() or not source_path.samefile(target_path):
                shutil.copy2(source_path, target_path)
            copied_paths.append(target_path.resolve())

        self.update_area_root_paths(to_area)
        return copied_paths

    def validate_materialized_project(self, area: str = "before") -> bool:
        files = tuple(self.update_area_root_paths(area))

        if not files:
            raise ValueError("El proyecto materializado no contiene archivos.")

        for path in files:
            if not path.exists():
                raise ValueError(f"No existe el archivo: {path}")
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise ValueError(f"No se pudo leer el archivo: {path}") from exc
            if path.suffix.lower() in self.TEXT_FILE_SUFFIXES and not is_readable(payload, text=True):
                raise ValueError(f"No se pudo leer el archivo de texto: {path}")

        return True

    # --- Query Methods ---

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

        return sorted(path.resolve() for path in root.rglob(search_pattern) if path.is_file())

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
