import importlib.util
import sys
import types
import os
from pathlib import Path

# Provide stub modules so recipe-extractor can be imported
sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))

# Prepare openai stub that records call parameters
record = {}
openai_stub = types.ModuleType("openai")

class ChatCompletions:
    @staticmethod
    def create(**kwargs):
        record.update(kwargs)
        # Mimic minimal response structure
        msg = types.SimpleNamespace(content="{}")
        choice = types.SimpleNamespace(message=msg)
        return types.SimpleNamespace(choices=[choice])

openai_stub.chat = types.SimpleNamespace(completions=ChatCompletions())
openai_stub.audio = types.SimpleNamespace()

sys.modules["openai"] = openai_stub

# Set dummy API key
os.environ.setdefault("OPENAI_API_KEY", "test-key")

spec = importlib.util.spec_from_file_location(
    "recipe_extractor", Path(__file__).resolve().parents[1] / "recipe-extractor.py"
)
recipe_extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe_extractor)


def test_healthiness_indicator_enum_in_schema():
    recipe_extractor.extract_recipe_with_gpt("dummy")

    schema = record["response_format"]["json_schema"]["schema"]
    enum_values = schema["properties"]["healthiness"]["properties"]["indicator"]["enum"]
    assert enum_values == ["healthy", "neutral", "unhealthy"]

