import uuid
from pathlib import Path
from typing import List, Iterable, TypedDict


# Define the strict internal structure of your dictionary for the type checker
class AreaStructure(TypedDict):
    rootPath: Path
    paths: List[Path]


class Session:
    SESSIONS_ROOT: Path = Path(__file__).resolve().parents[3] / "workspace" / "sessions"

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

    # --- Query Methods ---

    def find_by_suffix(self, area: str, suffixes: Iterable[str]) -> List[Path]:
        """
        Filters and gathers Paths by their file extensions inside a specific area.
        Uses structural pattern matching to extract the target path list.
        """
        valid_suffixes = {
            s.lower() if s.startswith('.') else f".{s.lower()}" for s in suffixes
        }

        match area.strip().lower():
            case "before":
                source_paths = self._before["paths"]
            case "after":
                source_paths = self._after["paths"]
            case "artifacts":
                source_paths = self._artifacts["paths"]
            case _:
                raise ValueError(
                    f"Invalid area: '{area}'. Choose 'before', 'after', or 'artifacts'."
                )

        return [p for p in source_paths if p.suffix in valid_suffixes]

    def get_path(self, name: str, area: str, suffix: str) -> Path:
        """
        Retrieves a single unique Path by its name, area, and suffix.
        All three parameters are strictly required. Uses structural pattern matching.
        """
        clean_name = name.strip()
        clean_suffix = suffix.lower() if suffix.startswith('.') else f".{suffix.lower()}"

        match area.strip().lower():
            case "before":
                source_paths = self._before["paths"]
            case "after":
                source_paths = self._after["paths"]
            case "artifacts":
                source_paths = self._artifacts["paths"]
            case _:
                raise ValueError(
                    f"Invalid area: '{area}'. Choose 'before', 'after', or 'artifacts'."
                )

        matches = [
            p for p in source_paths
            if p.name == clean_name and p.suffix == clean_suffix
        ]

        if not matches:
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
