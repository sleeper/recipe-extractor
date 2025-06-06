# Recipe Extractor 🍳

Extract structured recipes from YouTube cooking videos using AI transcription and analysis.

## Features ✨

- 🎥 Download audio from YouTube/Instagram cooking videos
- 🎙️ Transcribe audio using OpenAI Whisper
- 🤖 Extract structured recipe information using GPT
- 🌍 Multi-language support (English/French output)
- 📄 Multiple output formats (JSON/Markdown)
- 🟢 Health assessment with visual indicators
- 🛡️ Anti-hallucination guardrails to prevent false ingredients
- 📝 Optional transcription saving for debugging

## Prerequisites 📋

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) package manager
- [FFmpeg](https://ffmpeg.org/) for audio processing
- OpenAI API key

### Installing Prerequisites

#### Install uv

```bash
# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Install FFmpeg

```bash
# On macOS (with Homebrew)
brew install ffmpeg

# On Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# On Windows (with Chocolatey)
choco install ffmpeg
```

## Setup 🚀

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd recipe-extractor
   ```

2. **Install dependencies**

   ```bash
   uv sync
   ```

3. **Set up OpenAI API key**

   Create a `.env` file in the project root:

   ```bash
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   ```

   Or export it as an environment variable:

   ```bash
   export OPENAI_API_KEY="your_openai_api_key_here"
   ```

   > 💡 Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)

## Usage 📚

### Basic Usage

```bash
# Extract recipe in English (default)
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123"

# Extract recipe in French
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123" --language french

# Output as Markdown instead of JSON
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123" --format markdown
```

### Advanced Usage

```bash
# Custom output filename
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123" --output my_recipe

# Save transcription for debugging
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123" --save-transcript

# Save transcription with custom filename
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123" --save-transcript debug.txt

# All options combined
uv run recipe-extractor.py "https://youtube.com/watch?v=abc123" \
  --output italian_pasta \
  --language english \
  --format markdown \
  --save-transcript transcript.txt
```

### Command Line Options

| Option              | Short | Description                          | Default             |
| ------------------- | ----- | ------------------------------------ | ------------------- |
| `--output`          | `-o`  | Output filename (without extension)  | `structured_recipe` |
| `--language`        | `-l`  | Output language (`english`/`french`) | `english`           |
| `--format`          | `-f`  | Output format (`json`/`markdown`)    | `json`              |
| `--save-transcript` |       | Save transcription to file           | Not saved           |
| `--help`            | `-h`  | Show help message                    |                     |

## Output Format 📋

### JSON Output

```json
{
  "title": "Chocolate Chip Cookies",
  "ingredients": [
    "2 cups all-purpose flour",
    "1 cup butter, softened",
    "1/2 cup brown sugar"
  ],
  "steps": [
    "Preheat oven to 375°F",
    "Mix flour and butter in a bowl",
    "Add brown sugar and mix well"
  ],
  "tips": [
    "Don't overmix the dough",
    "Chill dough for 30 minutes before baking"
  ],
  "servings": "24 cookies",
  "healthiness": {
    "indicator": "🟡 Yellow",
    "rationale": "Moderate sugar content but includes some whole ingredients"
  }
}
```

### Markdown Output

```markdown
# Chocolate Chip Cookies

**Servings:** 24 cookies

## Ingredients

- 2 cups all-purpose flour
- 1 cup butter, softened
- 1/2 cup brown sugar

## Instructions

1. Preheat oven to 375°F
2. Mix flour and butter in a bowl
3. Add brown sugar and mix well

## Tips & Tricks

- Don't overmix the dough
- Chill dough for 30 minutes before baking

## Health Assessment

🟡 Yellow Moderate sugar content but includes some whole ingredients
```

## Health Indicators 🎯

- 🟢 **Green**: Healthy recipe with nutritious ingredients
- 🟡 **Yellow**: Moderate healthiness, some processed ingredients
- 🔴 **Red**: High in sugar, saturated fats, or heavily processed

## Supported Platforms 🌐

- YouTube videos
- Instagram Reels
- Any platform supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Error Handling 🛠️

### Common Issues

1. **Missing OpenAI API Key**

   ```
   Error: OPENAI_API_KEY not set
   ```

   Solution: Set up your `.env` file or environment variable

2. **FFmpeg Not Found**

   ```
   Error: FFmpeg not found
   ```

   Solution: Install FFmpeg (see Prerequisites)

3. **Invalid Video URL**
   ```
   Error: Unable to download video
   ```
   Solution: Check the URL and ensure the video is publicly accessible

### Debug Mode

Use `--save-transcript` to debug transcription issues:

```bash
uv run recipe-extractor.py "video-url" --save-transcript debug.txt
```

Then review `debug.txt` to see the raw transcription.

## Contributing 🤝

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License 📝

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏

- [OpenAI](https://openai.com/) for Whisper and GPT models
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video downloading
- [uv](https://docs.astral.sh/uv/) for fast Python package management
