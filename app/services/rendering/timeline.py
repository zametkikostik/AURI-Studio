"""
Работа с монтажным планом: JSON ↔ OpenTimelineIO (OTIO).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import opentimelineio as otio
    HAS_OTIO = True
except ImportError:
    HAS_OTIO = False
    otio = None  # type: ignore


def plan_to_otio(plan: Dict[str, Any], source_map: Dict[str, str] | None = None) -> "otio.schema.Timeline":
    if not HAS_OTIO:
        raise RuntimeError("opentimelineio не установлен. pip install opentimelineio")

    source_map = source_map or {}
    timeline = otio.schema.Timeline(name=plan.get("title") or "AURI Timeline")
    track = otio.schema.Track(name="Video", kind=otio.schema.TrackKind.Video)
    timeline.tracks.append(track)

    rate = 30.0

    for i, clip in enumerate(plan.get("clips", [])):
        start = float(clip["start"])
        end = float(clip["end"])
        speed = float(clip.get("speed", 1.0))
        src_id = clip.get("source_id", "main")
        media_path = source_map.get(src_id)

        available = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(start * rate, rate),
            duration=otio.opentime.RationalTime((end - start) * rate, rate),
        )

        media_ref = None
        if media_path:
            media_ref = otio.schema.ExternalReference(target_url=Path(media_path).resolve().as_uri())

        otio_clip = otio.schema.Clip(
            name=f"clip_{i:03d}",
            media_reference=media_ref,
            source_range=available,
        )
        otio_clip.metadata["auri"] = {
            "speed": speed,
            "transition": clip.get("transition", "cut"),
            "reason": clip.get("reason", ""),
            "source_id": src_id,
        }

        transition = clip.get("transition", "cut")
        if i > 0 and transition and transition != "cut":
            dur = float(clip.get("transition_duration", 0.5))
            tr = otio.schema.Transition(
                name=transition,
                transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve
                if transition in ("dissolve", "fade")
                else otio.schema.TransitionTypes.Custom,
                in_offset=otio.opentime.RationalTime(dur * rate / 2, rate),
                out_offset=otio.opentime.RationalTime(dur * rate / 2, rate),
            )
            tr.metadata["auri_type"] = transition
            track.append(tr)

        track.append(otio_clip)

    audio = plan.get("audio") or {}
    if audio.get("music") and audio["music"].get("path"):
        audio_track = otio.schema.Track(name="Music", kind=otio.schema.TrackKind.Audio)
        music_path = audio["music"]["path"]
        media_ref = otio.schema.ExternalReference(target_url=Path(music_path).resolve().as_uri())
        total_dur = sum(
            (float(c["end"]) - float(c["start"])) / float(c.get("speed", 1.0))
            for c in plan.get("clips", [])
        )
        music_clip = otio.schema.Clip(
            name="bg_music",
            media_reference=media_ref,
            source_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(0, rate),
                duration=otio.opentime.RationalTime(total_dur * rate, rate),
            ),
        )
        music_clip.metadata["auri"] = {
            "volume": audio["music"].get("volume", 0.3),
            "duck": audio["music"].get("duck", True),
        }
        audio_track.append(music_clip)
        timeline.tracks.append(audio_track)

    for ov in plan.get("overlays") or []:
        if ov.get("type") != "text":
            continue
        marker = otio.schema.Marker(
            name=ov.get("content", "")[:40],
            marked_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(float(ov.get("start", 0)) * rate, rate),
                duration=otio.opentime.RationalTime(
                    (float(ov.get("end", 0)) - float(ov.get("start", 0))) * rate, rate
                ),
            ),
            color=otio.schema.MarkerColor.RED,
        )
        marker.metadata["auri_overlay"] = ov
        timeline.tracks[0].markers.append(marker)

    return timeline


def otio_to_plan(timeline: "otio.schema.Timeline") -> Dict[str, Any]:
    if not HAS_OTIO:
        raise RuntimeError("opentimelineio не установлен")

    rate = 30.0
    clips = []
    for track in timeline.tracks:
        if track.kind != otio.schema.TrackKind.Video:
            continue
        pending_transition = "cut"
        pending_dur = 0.5
        for item in track:
            if isinstance(item, otio.schema.Transition):
                pending_transition = item.metadata.get("auri_type", "dissolve")
                pending_dur = (item.in_offset + item.out_offset).to_seconds()
                continue
            if not isinstance(item, otio.schema.Clip):
                continue
            meta = item.metadata.get("auri", {})
            src_range = item.source_range
            start = src_range.start_time.to_seconds() if src_range else 0.0
            end = start + (src_range.duration.to_seconds() if src_range else 0.0)
            clips.append({
                "source_id": meta.get("source_id", "main"),
                "start": round(start, 3),
                "end": round(end, 3),
                "speed": meta.get("speed", 1.0),
                "transition": pending_transition,
                "transition_duration": pending_dur,
                "reason": meta.get("reason", ""),
            })
            pending_transition = "cut"

    overlays = []
    if timeline.tracks:
        for marker in timeline.tracks[0].markers:
            ov = marker.metadata.get("auri_overlay")
            if ov:
                overlays.append(ov)

    music = None
    for track in timeline.tracks:
        if track.kind == otio.schema.TrackKind.Audio:
            for item in track:
                if isinstance(item, otio.schema.Clip):
                    meta = item.metadata.get("auri", {})
                    ref = item.media_reference
                    path = None
                    if ref and hasattr(ref, "target_url"):
                        path = ref.target_url.replace("file://", "")
                    music = {
                        "path": path,
                        "volume": meta.get("volume", 0.3),
                        "duck": meta.get("duck", True),
                    }
                    break

    return {
        "title": timeline.name or "AURI Timeline",
        "clips": clips,
        "overlays": overlays,
        "audio": {
            "keep_original": True,
            "music": music,
        },
        "notes": "Imported from OTIO",
    }


def save_otio(plan: Dict[str, Any], path: str | Path, source_map: Dict[str, str] | None = None) -> Path:
    path = Path(path)
    timeline = plan_to_otio(plan, source_map)
    otio.adapters.write_to_file(timeline, str(path))
    return path


def load_otio(path: str | Path) -> Dict[str, Any]:
    timeline = otio.adapters.read_from_file(str(path))
    return otio_to_plan(timeline)


def save_plan_json(plan: Dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_plan_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
