"""
Продвинутый FFmpeg-рендерер:
- нарезка + скорость
- переходы: cut, fade, dissolve, wipeleft, wiperight, slideleft, slideright, circlecrop, pixelize ...
- фоновая музыка + ducking
- текстовые оверлеи
"""
from __future__ import annotations

import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List

from app.config import settings

logger = logging.getLogger("auri.render")

XFADE_TRANSITIONS = {
    "fade", "dissolve",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite",
    "radial", "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circleopen", "circleclose", "vertopen", "vertclose",
    "horzopen", "horzclose", "pixelize",
    "diagtl", "diagtr", "diagbl", "diagbr",
    "hlslice", "hrslice", "vuslice", "vdslice",
    "hblur", "fadegrays", "wipetl", "wipetr", "wipebl", "wipebr",
    "squeezeh", "squeezev", "zoomin",
}


class FFmpegEngine:
    def __init__(self):
        self.ffmpeg = settings.FFMPEG_PATH

    def render(
        self,
        plan: Dict[str, Any],
        source_map: Dict[str, str],
        output_path: str | Path,
        keep_temp: bool = False,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="auri_render_"))

        try:
            clips = plan.get("clips") or []
            if not clips:
                raise ValueError("План не содержит клипов")

            clip_files: List[Path] = []
            clip_durations: List[float] = []

            for i, clip in enumerate(clips):
                src = source_map.get(clip.get("source_id", "main"))
                if not src or not Path(src).exists():
                    raise FileNotFoundError(f"Source not found: {clip.get('source_id')}")

                start = float(clip["start"])
                end = float(clip["end"])
                speed = max(0.5, min(2.0, float(clip.get("speed", 1.0))))
                duration = (end - start) / speed
                clip_durations.append(duration)

                out_clip = temp_dir / f"clip_{i:03d}.mp4"
                vfilter = f"setpts={1/speed}*PTS"
                afilter = f"atempo={speed}"

                cmd = [
                    self.ffmpeg, "-y",
                    "-ss", f"{start:.3f}",
                    "-to", f"{end:.3f}",
                    "-i", src,
                    "-filter:v", vfilter,
                    "-filter:a", afilter,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(out_clip),
                ]
                logger.info(f"Cut clip {i}: {start:.2f}-{end:.2f}s speed={speed} -> {duration:.2f}s")
                self._run(cmd)
                clip_files.append(out_clip)

            has_transitions = any(
                (c.get("transition") or "cut") != "cut" for c in clips[1:]
            )

            if has_transitions and len(clip_files) > 1:
                intermediate = self._render_with_xfade(
                    clip_files, clips, clip_durations, temp_dir
                )
            else:
                intermediate = self._simple_concat(clip_files, temp_dir)

            audio_cfg = plan.get("audio") or {}
            music = audio_cfg.get("music")
            if music and music.get("path") and Path(music["path"]).exists():
                intermediate = self._mix_music(
                    intermediate,
                    music_path=music["path"],
                    volume=float(music.get("volume", 0.28)),
                    duck=bool(music.get("duck", True)),
                    temp_dir=temp_dir,
                )

            overlays = [o for o in (plan.get("overlays") or []) if o.get("type") == "text"]
            if overlays:
                intermediate = self._apply_text_overlays(intermediate, overlays, temp_dir)

            shutil.copy2(intermediate, output_path)
            logger.info(f"Render complete -> {output_path}")
            return output_path

        finally:
            if not keep_temp:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _simple_concat(self, clip_files: List[Path], temp_dir: Path) -> Path:
        concat_list = temp_dir / "concat.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for cf in clip_files:
                f.write(f"file '{cf.resolve().as_posix()}'\n")

        out = temp_dir / "concat.mp4"
        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out),
        ]
        self._run(cmd)
        return out

    def _render_with_xfade(
        self,
        clip_files: List[Path],
        clips: List[Dict],
        durations: List[float],
        temp_dir: Path,
    ) -> Path:
        n = len(clip_files)
        inputs: List[str] = []
        for cf in clip_files:
            inputs.extend(["-i", str(cf)])

        v_filters = []
        a_filters = []
        prev_v = "[0:v]"
        prev_a = "[0:a]"
        offset = 0.0

        for i in range(1, n):
            transition = (clips[i].get("transition") or "dissolve").lower()
            if transition not in XFADE_TRANSITIONS:
                transition = "dissolve"
            tdur = float(clips[i].get("transition_duration", 0.5))
            tdur = max(0.15, min(tdur, durations[i - 1] * 0.4, durations[i] * 0.4))

            offset += durations[i - 1] - tdur

            v_out = f"[v{i}]"
            a_out = f"[a{i}]"

            v_filters.append(
                f"{prev_v}[{i}:v]xfade=transition={transition}:duration={tdur:.3f}:offset={offset:.3f}{v_out}"
            )
            a_filters.append(
                f"{prev_a}[{i}:a]acrossfade=d={tdur:.3f}{a_out}"
            )
            prev_v = v_out
            prev_a = a_out

        filter_complex = ";".join(v_filters + a_filters)
        out = temp_dir / "xfade.mp4"

        cmd = [
            self.ffmpeg, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", prev_v,
            "-map", prev_a,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]
        logger.info(f"xfade chain with {n} clips")
        self._run(cmd)
        return out

    def _mix_music(
        self,
        video_path: Path,
        music_path: str | Path,
        volume: float,
        duck: bool,
        temp_dir: Path,
    ) -> Path:
        out = temp_dir / "with_music.mp4"
        volume = max(0.0, min(1.0, volume))

        if duck:
            filter_complex = (
                f"[1:a]volume={volume}[music];"
                f"[0:a][music]sidechaincompress=threshold=0.02:ratio=6:attack=50:release=300[aout]"
            )
        else:
            filter_complex = (
                f"[1:a]volume={volume}[music];"
                f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(music_path),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(out),
        ]
        logger.info(f"Mixing music (volume={volume}, duck={duck})")
        self._run(cmd)
        return out

    def _apply_text_overlays(
        self,
        video_path: Path,
        overlays: List[Dict],
        temp_dir: Path,
    ) -> Path:
        filters = []
        for ov in overlays:
            text = (
                str(ov.get("content", ""))
                .replace("\\", "\\\\")
                .replace("'", r"\\'")
                .replace(":", r"\\:")
                .replace("%", r"\\%")
            )
            start = float(ov.get("start", 0))
            end = float(ov.get("end", start + 3))
            pos = ov.get("position", "bottom")
            style = ov.get("style") or {}
            fontsize = int(style.get("fontsize", 42))
            fontcolor = style.get("fontcolor", "white")

            y_map = {
                "bottom": "h-th-60",
                "top": "50",
                "center": "(h-th)/2",
            }
            y = y_map.get(pos, "h-th-60")

            filters.append(
                f"drawtext=text='{text}':fontsize={fontsize}:fontcolor={fontcolor}:"
                f"borderw=3:bordercolor=black@0.75:x=(w-tw)/2:y={y}:"
                f"enable='between(t\\,{start}\\,{end})'"
            )

        filter_str = ",".join(filters)
        out = temp_dir / "with_text.mp4"
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", filter_str,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out),
        ]
        self._run(cmd)
        return out

    def _run(self, cmd: List[str]) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed (code {result.returncode}):\n"
                f"CMD: {' '.join(cmd[:12])}...\n"
                f"STDERR:\n{result.stderr[-2500:]}"
            )
