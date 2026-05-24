import re
import sys
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def _extract_video_id(url: str) -> str:
    patterns = [
        r"youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract a video ID from: {url!r}")


def fetch_youtube_transcript(url: str) -> tuple[str, dict]:
    video_id = _extract_video_id(url)
    try:
        segments = YouTubeTranscriptApi().fetch(video_id, languages=["en"]).to_raw_data()
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        raise RuntimeError(
            f"No English transcript available for video '{video_id}'. "
            "Try a different video — lectures, talks, and tutorials usually have captions."
        ) from e

    text = " ".join(seg["text"] for seg in segments)
    duration = segments[-1]["start"] + segments[-1].get("duration", 0)
    metadata = {
        "url": url,
        "video_id": video_id,
        "duration_seconds": round(duration, 2),
        "segment_count": len(segments),
    }
    return text, metadata


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <youtube_url>")
        sys.exit(1)
    transcript, meta = fetch_youtube_transcript(sys.argv[1])
    print(f"Metadata: {meta}")
    print(f"\nTranscript (first 500 chars):\n{transcript[:500]}")
