"""Rendering package — lazy imports so CI/import works without heavy deps present."""

def __getattr__(name: str):
    if name == "FFmpegEngine":
        from .ffmpeg_engine import FFmpegEngine
        return FFmpegEngine
    if name in (
        "plan_to_otio", "otio_to_plan", "save_otio", "load_otio",
        "save_plan_json", "load_plan_json", "HAS_OTIO",
    ):
        from . import timeline as tl
        return getattr(tl, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "FFmpegEngine",
    "plan_to_otio",
    "otio_to_plan",
    "save_otio",
    "load_otio",
    "save_plan_json",
    "load_plan_json",
    "HAS_OTIO",
]
