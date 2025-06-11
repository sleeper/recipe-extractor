import yt_dlp
import openai
import os
import sys
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
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

def get_youtube_transcript(video_id, languages=None):
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
        except Exception as e:
            print("⚠️ Issue while getting transcripts: ", e)
            return None
        return " ".join(seg.text for seg in segments)

    # First try preferred languages
    for lang in languages:
        try:
            t = transcript_list.find_transcript([lang])
        except Exception:
            t = None
        if t:
            text = fetch_text(t)
            if text:
                return text

    # Fall back to the first available transcript
    for t in transcript_list:
        text = fetch_text(t)
        if text:
            return text

    return None

def get_post_text(info):
    """Return video description or caption."""
    for key in ("description", "caption", "summary"):
        text = info.get(key)
        if text:
            return text
    return ""

def get_caption_languages(info):
    """Return list of caption language codes from video metadata."""
    languages = []
    for key in ("subtitles", "automatic_captions"):
        for lang in info.get(key, {}):
            if lang not in languages:
                languages.append(lang)
    if info.get("language") and info["language"] not in languages:
        languages.append(info["language"])
    return languages

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

def convert_to_markdown(recipe_json, language="english"):
    """Convert recipe JSON to markdown format with localized section headings."""
    recipe = json.loads(recipe_json)

    headings = {
        "english": {
            "servings": "Servings",
            "ingredients": "Ingredients",
            "instructions": "Instructions",
            "tips": "Tips & Tricks",
            "health": "Health Assessment",
        },
        "french": {
            "servings": "Portions",
            "ingredients": "Ingr\u00e9dients",
            "instructions": "Instructions",
            "tips": "Astuces",
            "health": "\u00c9valuation de la sant\u00e9",
        },
    }

    labels = headings.get(language.lower(), headings["english"])

    markdown = f"# {recipe['title']}\n\n"

    markdown += f"**{labels['servings']}:** {recipe['servings']}\n\n"

    markdown += f"## {labels['ingredients']}\n"
    for ingredient in recipe['ingredients']:
        markdown += f"- {ingredient}\n"
    markdown += "\n"

    markdown += f"## {labels['instructions']}\n"
    for i, step in enumerate(recipe['steps'], 1):
        markdown += f"{i}. {step}\n"
    markdown += "\n"

    if recipe['tips']:
        markdown += f"## {labels['tips']}\n"
        for tip in recipe['tips']:
            markdown += f"- {tip}\n"
        markdown += "\n"

    markdown += f"## {labels['health']}\n"
    markdown += f"{recipe['healthiness']['indicator']} {recipe['healthiness']['rationale']}\n"

    return markdown


def extract_recipe(url, language="english", output_format="json", save_transcript=None):
    """High-level helper to extract a recipe from a URL and return it as a string."""
    print(f"🎯 Extracting from URL: {url}")

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

    print(f"🤖 Extracting recipe using AI (language: {language})...")
    structured_recipe = extract_recipe_with_gpt(transcript, language)

    if output_format == "markdown":
        return convert_to_markdown(structured_recipe, language)
    else:
        # ensure valid JSON formatting
        return json.dumps(json.loads(structured_recipe), ensure_ascii=False)


def run_rest_server(host="0.0.0.0", port=8000, *, serve_forever=True):
    """Run a very small REST API server.

    Parameters
    ----------
    host : str
        Host interface to bind.
    port : int
        Port to listen on.
    serve_forever : bool, optional
        If ``True`` (default) block and serve forever. When ``False`` the
        configured ``HTTPServer`` instance is returned without entering the
        serving loop. This is useful for unit tests.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/extract":
                self.send_error(404, "Not Found")
                return

            qs = parse_qs(parsed.query)
            url = qs.get("url", [None])[0]
            if not url:
                self.send_error(400, "Missing url parameter")
                return

            language = qs.get("language", ["english"])[0]
            fmt = qs.get("format", ["json"])[0]

            try:
                result = extract_recipe(url, language, fmt)
            except Exception as e:
                self.send_error(500, str(e))
                return

            if fmt == "markdown":
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(result.encode("utf-8"))

    server = HTTPServer((host, port), Handler)
    print(f"🚀 REST API running on http://{host}:{port}")
    if serve_forever:
        server.serve_forever()
    return server


def run_mcp_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    transport: str = "stdio",
    *,
    serve_forever: bool = True,
):
    """Run an MCP server using the official Python SDK.

    Parameters
    ----------
    host : str
        Host interface to bind for network transports.
    port : int
        Port to listen on for network transports.
    transport : {'stdio', 'streamable-http'}
        Transport mechanism to use.
    serve_forever : bool, optional
        When ``True`` (default) the server runs and blocks. When ``False`` the
        :class:`FastMCP` instance is returned for manual control and testing.
    """

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("Recipe Extractor", host=host, port=port)

    @mcp.tool(name="extract_recipe")
    def extract(url: str, language: str = "english", format: str = "json") -> str:
        return extract_recipe(url, language, format)

    if serve_forever:
        mcp.run(transport)
    return mcp

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
    parser.add_argument('url', nargs='?', help='YouTube URL of the cooking video')
    parser.add_argument('--output', '-o', help='Output file name (without extension, will be added based on format)')
    parser.add_argument('--language', '-l', choices=['english', 'french'], default='english',
                       help='Language for recipe extraction (default: english)')
    parser.add_argument('--format', '-f', choices=['json', 'markdown'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--save-transcript', nargs='?', const='transcription.txt', metavar='FILE',
                       help='Save transcription to file (default: transcription.txt if no filename provided)')
    parser.add_argument('--server', '-s', action='store_true', help='Run REST API server')
    parser.add_argument('--mcp', '-m', action='store_true', help='Run MCP server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Server port (default: 8000)')
    parser.add_argument('--mcp-transport', choices=['stdio', 'streamable-http'], default='stdio',
                        help='Transport for MCP server (default: stdio)')
    
    args = parser.parse_args()

    if args.server:
        run_rest_server(args.host, args.port)
        return
    if args.mcp:
        run_mcp_server(args.host, args.port, args.mcp_transport)
        return

    if not args.url:
        parser.error("the following arguments are required: url")

    print(f"🎯 Starting recipe extraction from: {args.url}")
    print(f"🌍 Language: {args.language}")
    print(f"📄 Format: {args.format}")
    print(f"💾 Output: {args.output or 'structured_recipe'}")
    print()
    
    info = fetch_video_info(args.url)
    post_text = get_post_text(info)

    caption_langs = get_caption_languages(info)
    transcript = get_youtube_transcript(info.get('id'), caption_langs)
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
        markdown_content = convert_to_markdown(structured_recipe, args.language)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"✅ Structured recipe saved as {filename}")

if __name__ == "__main__":
    main()

