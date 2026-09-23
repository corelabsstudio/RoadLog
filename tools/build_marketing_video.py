"""Make a short vertical MP4 from an AI-created still, without a paid video API.

Reuses the locally verified FFmpeg binary from ai-influencer-7day. This CLI is
not run on Railway. The input image and optional narration are supplied by the
operator's free creative workflow; this program does not claim to generate them.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FFMPEG = ROOT.parent / "ai-influencer-7day" / "runtime" / "bin" / "ffmpeg.exe"


def build_video(image: Path, output: Path, *, audio: Path | None = None, seconds: int = 8, ffmpeg: Path = DEFAULT_FFMPEG) -> Path:
    image, output, ffmpeg = Path(image).resolve(), Path(output).resolve(), Path(ffmpeg).resolve()
    if not ffmpeg.is_file():
        raise FileNotFoundError("로컬 FFmpeg가 없습니다. AI 인플루언서 설치 기록을 확인해 주세요.")
    if not image.is_file() or image.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("기존 AI 생성 JPEG/PNG 이미지 파일이 필요합니다.")
    if audio is not None:
        audio = Path(audio).resolve()
        if not audio.is_file():
            raise FileNotFoundError("내레이션 파일이 없습니다.")
    if output.exists():
        raise FileExistsError("기존 결과를 덮어쓰지 않습니다. 다른 출력 경로를 지정해 주세요.")
    if output.suffix.lower() != ".mp4" or not 2 <= seconds <= 15:
        raise ValueError("출력은 MP4, 길이는 2~15초여야 합니다.")
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = seconds * 25
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(image)]
    if audio is not None:
        command += ["-i", str(audio)]
    command += ["-filter:v", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,zoompan=z='min(zoom+0.0008,1.1)':d=1:s=720x1280:fps=25,format=yuv420p",
                "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "24"]
    if audio is not None:
        command += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k", "-t", str(seconds)]
    else:
        command += ["-an"]
    command += [str(output)]
    try:
        subprocess.run(command, check=True, timeout=240, capture_output=True)
        if not output.is_file() or output.stat().st_size < 1024:
            raise RuntimeError("영상 파일이 생성되지 않았습니다.")
        subprocess.run([str(ffmpeg), "-v", "error", "-i", str(output), "-f", "null", "NUL"], check=True, timeout=60, capture_output=True)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="무료 로컬 도구로 AI 생성 이미지에 움직임을 주어 세로 MP4 제작")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=8)
    args = parser.parse_args()
    print(build_video(args.image, args.output, audio=args.audio, seconds=args.seconds))
