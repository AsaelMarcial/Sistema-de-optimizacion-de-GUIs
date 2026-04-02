from __future__ import annotations

from dataclasses import dataclass

from coloraide.everything import ColorAll


@dataclass(frozen=True)
class GamutStrategy:
    name: str
    method: str
    pspace: str | None = None

    def fit(self, color: ColorAll, *, space: str) -> ColorAll:
        kwargs: dict[str, str] = {"space": space, "method": self.method}
        if self.pspace is not None:
            kwargs["pspace"] = self.pspace
        return color.fit(**kwargs)
