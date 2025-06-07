import yt_dlp
import openai
import os
import sys
import argparse
import json
from dotenv import load_dotenv

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:  # pragma: no cover - optional dep may not be installed
    YouTubeTranscriptApi = None
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY not set")
    sys.exit(1)
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

def fetch_video_info(url):
    """Return video metadata without downloading the file."""
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        return ydl.extract_info(url, download=False)

def get_youtube_transcript(video_id, languages=("en", "en-US", "en-GB")):
    """Fetch transcript text from YouTube if available."""
    if not YouTubeTranscriptApi:
        print("⚠️  youtube-transcript-api not installed; skipping transcript fetch")
        return None

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except Exception as e:  # pragma: no cover - network dependent
        print(f"⚠️  Could not list transcripts: {e}")
        return None

    for lang in languages:
        try:
            t = None
            try:
                t = transcript_list.find_manually_created_transcript([lang])
            except Exception:
                t = transcript_list.find_generated_transcript([lang])
            segments = t.fetch() if t else None
        except Exception:
            segments = None
        if segments:
            return " ".join(seg.get('text', '') for seg in segments)

    return None

def get_post_text(info):
    """Return video description or caption."""
    for key in ("description", "caption", "summary"):
        text = info.get(key)
        if text:
            return text
    return ""

def transcribe_whisper(file_path):
    openai.api_key = OPENAI_API_KEY
    with open(file_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            # model="whisper-1",
            model="gpt-4o-mini-transcribe",
            file=audio_file
        )
    return transcript.text

def extract_recipe_with_gpt(transcript, language="english"):
    openai.api_key = OPENAI_API_KEY
    
    # Single English prompt with optional language instruction
    prompt = f"""
You are extracting recipe information from a video transcription. Follow these rules STRICTLY:

1. INGREDIENTS: Extract ONLY ingredients explicitly mentioned. Do NOT add common ingredients like salt, pepper, oil, rice, etc. unless specifically mentioned.
2. STEPS: Include ONLY the cooking steps described in the video.
3. SERVINGS: Only mention if the speaker states the number of servings.
4. TIPS: Include ONLY if the speaker gives specific tips in the video. Do NOT add general cooking knowledge.
5. HEALTH: Evaluate based on the ingredients actually mentioned.

CRITICAL: If you add ANY ingredient, step, or tip not explicitly stated in the transcription, you are making an error. When in doubt, leave it out.

Transcription:
\"\"\"{transcript}\"\"\"
"""
    
    # Always add explicit language instruction
    language_names = {
        "english": "English",
        "french": "French"
    }
    output_language = language_names.get(language, language.title())
    prompt += f"\n\nIMPORTANT: Regardless of the language used in the transcription, please provide your response (ingredients, steps, tips, etc.) in {output_language}."
    print(f"🌍 Added explicit language instruction: output in {output_language}")
    
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
                    "healthiness": {
                        "type": "object",
                        "properties": {
                            "indicator": {"type": "string"},
                            "rationale": {"type": "string"}
                        },
                        "required": ["indicator", "rationale"]
                    }
                },
                "required": ["title", "ingredients", "steps", "tips", "servings", "healthiness"]
            }
        }
    }
    response = openai.chat.completions.create(
        # model="gpt-4o",
        model="gpt-4o-mini",
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
    
    markdown += "## Health Assessment\n"
    markdown += f"{recipe['healthiness']['indicator']} {recipe['healthiness']['rationale']}\n"
    
    return markdown

def main():
    parser = argparse.ArgumentParser(
        description='Extract recipes from YouTube cooking videos',
        epilog='''
Examples:
  uv run %(prog)s "https://youtube.com/watch?v=abc123"
  uv run %(prog)s "https://youtube.com/watch?v=abc123" --output my_recipe
  uv run %(prog)s "https://youtube.com/watch?v=abc123" --save-transcript
  uv run %(prog)s "https://youtube.com/watch?v=abc123" --save-transcript audio_transcript.txt
  uv run %(prog)s "https://youtube.com/watch?v=abc123" -o pasta -l french -f markdown --save-transcript
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('url', help='YouTube URL of the cooking video')
    parser.add_argument('--output', '-o', help='Output file name (without extension, will be added based on format)')
    parser.add_argument('--language', '-l', choices=['english', 'french'], default='english',
                       help='Language for recipe extraction (default: english)')
    parser.add_argument('--format', '-f', choices=['json', 'markdown'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--save-transcript', nargs='?', const='transcription.txt', metavar='FILE',
                       help='Save transcription to file (default: transcription.txt if no filename provided)')
    
    args = parser.parse_args()
    
    print(f"🎯 Starting recipe extraction from: {args.url}")
    print(f"🌍 Language: {args.language}")
    print(f"📄 Format: {args.format}")
    print(f"💾 Output: {args.output or 'structured_recipe'}")
    print()
    
    info = fetch_video_info(args.url)
    post_text = get_post_text(info)

    transcript = get_youtube_transcript(info.get('id'))
    if transcript:
        print("📝 Using existing YouTube transcript")
    else:
        print("⬇️  Downloading audio...")
        download_audio_with_ytdlp(args.url)

        print("🎙️  Transcribing audio...")
        transcript = transcribe_whisper(AUDIO_FILE)
        print(f"📏 Transcription length: {len(transcript)} characters")

    combined = (post_text + "\n\n" + transcript).strip()
    
    # Save transcription if requested
    if args.save_transcript:
        with open(args.save_transcript, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"📝 Transcription saved to {args.save_transcript} for review")
    print()
    
    # Clean up audio file after transcription
    try:
        os.remove(AUDIO_FILE)
        print("🧹 Audio file cleaned up.")
    except OSError:
        print("⚠️  Warning: Could not delete audio file.")
    
    print(f"🤖 Extracting recipe using AI (language: {args.language})...")
    structured_recipe = extract_recipe_with_gpt(combined, args.language)
    
    print("✅ AI extraction completed")
    
    # Determine output filename
    if args.output:
        base_filename = args.output
    else:
        base_filename = "structured_recipe"
    
    # Save output based on format
    if args.format == 'json':
        filename = f"{base_filename}.json"
        with open(filename, "w", encoding="utf-8") as f:
            # Parse and reformat JSON to ensure proper formatting
            recipe_dict = json.loads(structured_recipe)
            json.dump(recipe_dict, f, indent=2, ensure_ascii=False)
        print(f"✅ Structured recipe saved as {filename}")
    else:  # markdown
        filename = f"{base_filename}.md"
        markdown_content = convert_to_markdown(structured_recipe)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"✅ Structured recipe saved as {filename}")

if __name__ == "__main__":
    main()

