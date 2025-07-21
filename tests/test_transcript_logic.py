import importlib.util
import sys
import types
import os
from pathlib import Path

# Stub optional dependencies so the module can be imported
sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
sys.modules.setdefault("openai", types.ModuleType("openai"))

os.environ.setdefault("OPENAI_API_KEY", "test-key")

spec = importlib.util.spec_from_file_location(
    "recipe_extractor", Path(__file__).resolve().parents[1] / "recipe-extractor.py"
)
recipe_extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe_extractor)
video_transcripts = sys.modules["video_transcripts"]

def test_is_youtube_url_detection():
    assert recipe_extractor.is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert recipe_extractor.is_youtube_url("https://youtu.be/abc")
    assert not recipe_extractor.is_youtube_url("https://instagram.com/reel/abc")

def test_main_only_uses_youtube_transcripts(tmp_path, monkeypatch):
    calls = {"yt": 0}

    def fake_fetch_info(url):
        return {"id": "abc"}

    monkeypatch.setattr(video_transcripts, "fetch_video_info", fake_fetch_info)
    monkeypatch.setattr(video_transcripts, "get_post_text", lambda info: "")
    monkeypatch.setattr(video_transcripts, "get_caption_languages", lambda info: [])

    def fake_get_transcript(video_id, langs=None):
        calls["yt"] += 1
        return "transcript"

    monkeypatch.setattr(video_transcripts, "get_youtube_transcript", fake_get_transcript)
    monkeypatch.setattr(video_transcripts, "download_audio_with_ytdlp", lambda url: None)
    monkeypatch.setattr(video_transcripts, "transcribe_whisper", lambda path: "audio")
    monkeypatch.setattr(recipe_extractor, "extract_recipe_with_gpt", lambda t, l: "{}")

    # YouTube URL should trigger transcript fetch
    monkeypatch.setattr(sys, "argv", [
        "prog",
        "https://youtube.com/watch?v=abc",
        "--output",
        str(tmp_path / "out")
    ])
    recipe_extractor.main()
    assert calls["yt"] == 1

    calls["yt"] = 0
    # Instagram URL should not attempt YouTube transcript
    monkeypatch.setattr(sys, "argv", [
        "prog",
        "https://instagram.com/reel/xyz",
        "--output",
        str(tmp_path / "out2")
    ])
    recipe_extractor.main()
    assert calls["yt"] == 0
