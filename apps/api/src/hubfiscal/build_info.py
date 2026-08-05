from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from . import __version__


@dataclass(frozen=True, slots=True)
class BuildInfo:
    version: str
    sha: str
    ref: str
    built_at: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def get_build_info() -> BuildInfo:
    return BuildInfo(
        version=__version__,
        sha=os.getenv("HUBFISCAL_BUILD_SHA", "development"),
        ref=os.getenv("HUBFISCAL_BUILD_REF", "local"),
        built_at=os.getenv("HUBFISCAL_BUILD_DATE", "unknown"),
    )
