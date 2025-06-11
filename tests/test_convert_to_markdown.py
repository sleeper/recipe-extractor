import json
import importlib.util
from pathlib import Path
import os
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-sdk" / "src"))

# Provide stub modules so the script can be imported without optional deps
sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))
sys.modules.setdefault("openai", types.ModuleType("openai"))

# Set dummy API key so recipe-extractor doesn't exit on import
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Dynamically load the convert_to_markdown function from recipe-extractor.py
spec = importlib.util.spec_from_file_location(
    "recipe_extractor", Path(__file__).resolve().parents[1] / "recipe-extractor.py"
)
recipe_extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe_extractor)
convert_to_markdown = recipe_extractor.convert_to_markdown

def test_convert_to_markdown_basic():
    sample = {
        "title": "Sample Recipe",
        "ingredients": ["1 cup flour", "2 eggs"],
        "steps": ["Mix ingredients", "Bake"],
        "tips": ["Let it cool"],
        "servings": "2",
        "healthiness": {"indicator": "🟢 Green", "rationale": "Very healthy"},
    }
    md = convert_to_markdown(json.dumps(sample))

    assert "# Sample Recipe" in md
    assert "**Servings:** 2" in md
    assert "## Ingredients" in md
    assert "- 1 cup flour" in md
    assert "## Instructions" in md
    assert "1. Mix ingredients" in md
    assert "## Tips & Tricks" in md
    assert "## Health Assessment" in md
    assert "🟢 Green Very healthy" in md


def test_convert_to_markdown_french_headings():
    sample = {
        "title": "Recette Exemple",
        "ingredients": ["1 tasse de farine"],
        "steps": ["M\u00e9langer"],
        "tips": [],
        "servings": "2",
        "healthiness": {"indicator": "🟢 Green", "rationale": "Tr\u00e8s sain"},
    }
    md = convert_to_markdown(json.dumps(sample), language="french")

    assert "**Portions:** 2" in md
    assert "## Ingr\u00e9dients" in md
