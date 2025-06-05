import yt_dlp
import openai
import os
import sys
import argparse
import json
from dotenv import load_dotenv
load_dotenv()

## TODO: manage the case where the key is not present
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
AUDIO_FILE = "audio.mp3"

def download_audio_with_ytdlp(url, out_file=AUDIO_FILE):
    # Remove extension from out_file since FFmpegExtractAudio will add it
    base_name = out_file.rsplit('.', 1)[0] if '.' in out_file else out_file
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': base_name,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'noplaylist': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def transcribe_whisper(file_path):
    openai.api_key = OPENAI_API_KEY
    with open(file_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text

def extract_recipe_with_gpt(transcript, language="english"):
    openai.api_key = OPENAI_API_KEY
    
    # Single English prompt with optional language instruction
    prompt = f"""
Here is the transcription of a cooking recipe video. Your task:
- Extract the list of ingredients (with quantities if mentioned)
- Break down the recipe steps
- Determine the number of servings if possible
- Provide one or two tips/tricks if possible
- Evaluate if the recipe is "healthy" or not (and explain why in one sentence)
- Provide a quick estimate of macronutrients (carbs, proteins, fats) per serving if possible, otherwise "N/A"

Transcription:
\"\"\"{transcript}\"\"\"
"""
    
    # Add language instruction if not English
    if language != "english":
        language_names = {
            "french": "French"
        }
        prompt += f"\n\nIMPORTANT: Please provide your response in {language_names.get(language, language.title())}."
    
    system_message = "You are a pedagogical chef and nutritionist."
    
    # Define JSON schema for structured output
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "recipe_extraction",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "tips": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "servings": {"type": "string"},
                    "healthiness": {"type": "string"},
                    "macros": {
                        "type": "object",
                        "properties": {
                            "calories": {"type": "string"},
                            "proteins": {"type": "string"},
                            "carbs": {"type": "string"},
                            "fats": {"type": "string"}
                        },
                        "required": ["calories", "proteins", "carbs", "fats"]
                    }
                },
                "required": ["title", "ingredients", "steps", "tips", "servings", "healthiness", "macros"]
            }
        }
    }
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        response_format=response_format
    )
    return response.choices[0].message.content

def convert_to_markdown(recipe_json):
    """Convert recipe JSON to markdown format"""
    recipe = json.loads(recipe_json)
    
    markdown = f"# {recipe['title']}\n\n"
    
    markdown += f"**Servings:** {recipe['servings']}\n\n"
    
    markdown += "## Ingredients\n"
    for ingredient in recipe['ingredients']:
        markdown += f"- {ingredient}\n"
    markdown += "\n"
    
    markdown += "## Instructions\n"
    for i, step in enumerate(recipe['steps'], 1):
        markdown += f"{i}. {step}\n"
    markdown += "\n"
    
    if recipe['tips']:
        markdown += "## Tips & Tricks\n"
        for tip in recipe['tips']:
            markdown += f"- {tip}\n"
        markdown += "\n"
    
    markdown += "## Nutritional Information\n"
    markdown += f"**Health Assessment:** {recipe['healthiness']}\n\n"
    markdown += "**Macros per serving:**\n"
    markdown += f"- Calories: {recipe['macros']['calories']}\n"
    markdown += f"- Proteins: {recipe['macros']['proteins']}\n"
    markdown += f"- Carbs: {recipe['macros']['carbs']}\n"
    markdown += f"- Fats: {recipe['macros']['fats']}\n"
    
    return markdown

def main():
    parser = argparse.ArgumentParser(
        description='Extract recipes from YouTube cooking videos',
        epilog='''
Examples:
  uv run %(prog)s "https://youtube.com/watch?v=abc123"
  uv run %(prog)s "https://youtube.com/watch?v=abc123" --language french
  uv run %(prog)s "https://youtube.com/watch?v=abc123" --format markdown
  uv run %(prog)s "https://youtube.com/watch?v=abc123" -l french -f markdown
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('url', help='YouTube URL of the cooking video')
    parser.add_argument('--language', '-l', choices=['english', 'french'], default='english',
                       help='Language for recipe extraction (default: english)')
    parser.add_argument('--format', '-f', choices=['json', 'markdown'], default='json',
                       help='Output format (default: json)')
    
    args = parser.parse_args()
    
    print("Downloading audio...")
    download_audio_with_ytdlp(args.url)
    
    print("Transcribing audio...")
    transcript = transcribe_whisper(AUDIO_FILE)
    
    # Clean up audio file after transcription
    try:
        os.remove(AUDIO_FILE)
        print("Audio file cleaned up.")
    except OSError:
        print("Warning: Could not delete audio file.")
    
    print("Extracting recipe using AI...")
    structured_recipe = extract_recipe_with_gpt(transcript, args.language)
    
    # Save output based on format
    if args.format == 'json':
        filename = "structured_recipe.json"
        with open(filename, "w", encoding="utf-8") as f:
            # Parse and reformat JSON to ensure proper formatting
            recipe_dict = json.loads(structured_recipe)
            json.dump(recipe_dict, f, indent=2, ensure_ascii=False)
        print(f"✅ Structured recipe saved as {filename}")
    else:  # markdown
        filename = "structured_recipe.md"
        markdown_content = convert_to_markdown(structured_recipe)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"✅ Structured recipe saved as {filename}")

if __name__ == "__main__":
    main()

