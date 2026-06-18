import subprocess
import os
from pathlib import Path

def extract_audio(video_path: str, audio_path: str, sample_rate: int = 16000):
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(sample_rate), "-ac", "1",
        audio_path, "-y"
    ], check=True, capture_output=True)

def get_video_duration(video_path: str) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ], check=True, capture_output=True, text=True)
    return float(result.stdout.strip())
