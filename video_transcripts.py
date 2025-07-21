import yt_dlp
import openai
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:  # pragma: no cover - optional dependency
    YouTubeTranscriptApi = None

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AUDIO_FILE = "audio.mp3"


def is_youtube_url(url: str) -> bool:
    """Return True if the URL points to YouTube."""
    host = urlparse(url).netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def download_audio_with_ytdlp(url: str, out_file: str = AUDIO_FILE) -> None:
    """Download the audio track from a video using yt-dlp."""
    base_name = out_file.rsplit(".", 1)[0] if "." in out_file else out_file
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": base_name,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": False,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def fetch_video_info(url: str) -> dict:
    """Return video metadata without downloading the file."""
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)


def get_youtube_transcript(video_id: str, languages=None) -> str | None:
    """Fetch transcript text from YouTube if available."""
    if not YouTubeTranscriptApi:
        print("⚠️  youtube-transcript-api not installed; skipping transcript fetch")
        return None

    ytt_api = YouTubeTranscriptApi()
    try:
        transcript_list = ytt_api.list(video_id)
    except Exception as e:  # pragma: no cover - network dependent
        print(f"⚠️  Could not list transcripts: {e}")
        return None

    languages = list(languages or [])

    def fetch_text(transcript):
        try:
            segments = transcript.fetch()
        except Exception as e:  # pragma: no cover - network dependent
            print("⚠️ Issue while getting transcripts: ", e)
            return None
        return " ".join(seg.text for seg in segments)

    for lang in languages:
        try:
            t = transcript_list.find_transcript([lang])
        except Exception:
            t = None
        if t:
            text = fetch_text(t)
            if text:
                return text

    for t in transcript_list:
        text = fetch_text(t)
        if text:
            return text
    return None


def get_post_text(info: dict) -> str:
    """Return video description or caption."""
    for key in ("description", "caption", "summary"):
        text = info.get(key)
        if text:
            return text
    return ""


def get_caption_languages(info: dict) -> list:
    """Return list of caption language codes from video metadata."""
    languages = []
    for key in ("subtitles", "automatic_captions"):
        for lang in info.get(key, {}):
            if lang not in languages:
                languages.append(lang)
    if info.get("language") and info["language"] not in languages:
        languages.append(info["language"])
    return languages


def transcribe_whisper(file_path: str) -> str:
    """Transcribe an audio file using OpenAI Whisper."""
    openai.api_key = OPENAI_API_KEY
    with open(file_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
        )
    return transcript.text


def extract_video_transcript(url: str, *, save_transcript: str | None = None) -> str:
    """Return combined post text and transcript for a video URL."""
    info = fetch_video_info(url)
    post_text = get_post_text(info)

    transcript = None
    if is_youtube_url(url):
        caption_langs = get_caption_languages(info)
        transcript = get_youtube_transcript(info.get("id"), caption_langs)
        if transcript:
            print("📝 Using existing YouTube transcript")

    if not transcript:
        print("⬇️  Downloading audio...")
        download_audio_with_ytdlp(url)
        print("🎙️  Transcribing audio...")
        transcript = transcribe_whisper(AUDIO_FILE)
        if save_transcript:
            with open(save_transcript, "w", encoding="utf-8") as f:
                f.write(transcript)

    try:
        os.remove(AUDIO_FILE)
    except OSError:
        pass

    combined = (post_text + "\n\n" + transcript).strip()
    return combined
