import yt_dlp
import openai
import os
import sys
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

def extract_recipe_with_gpt(transcript):
    openai.api_key = OPENAI_API_KEY
    prompt = f"""
Voici la transcription d'une vidéo de recette de cuisine. Ta tâche :
- Extrais la liste des ingrédients (avec quantités si mentionnées)
- Découpe les étapes de la recette
- Déduis le nombre de portions si possible
- Donne un ou deux conseils/astuces si possible
- Évalue si la recette est "healthy" ou non (et explique pourquoi en une phrase)
- Propose une estimation rapide des macronutriments (glucides, protéines, lipides) par portion si possible, sinon "N/A"

Formate la sortie ainsi :
{{
  "titre": "...",
  "ingredients": ["..."],
  "etapes": ["..."],
  "astuces": ["..."],
  "portions": "...",
  "healthiness": "...",
  "macros": {{
    "calories": "...",
    "proteines": "...",
    "glucides": "...",
    "lipides": "..."
  }}
}}
----------------------
Transcription :
\"\"\"{transcript}\"\"\"
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Tu es un chef de cuisine pédagogue et nutritionniste."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <URL>")
        return
    url = sys.argv[1]
    print("Téléchargement audio...")
    download_audio_with_ytdlp(url)
    print("Transcription...")
    transcript = transcribe_whisper(AUDIO_FILE)
    print("Extraction de la recette (LLM)...")
    structured_recipe = extract_recipe_with_gpt(transcript)
    with open("recette_structurée.json", "w", encoding="utf-8") as f:
        f.write(structured_recipe)
    print("✅ Recette structurée sauvegardée dans recette_structurée.json")

if __name__ == "__main__":
    main()

