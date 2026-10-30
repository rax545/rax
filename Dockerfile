FROM python:3.12-slim

WORKDIR /app

# FFmpeg is required by discord.py for VC playback.  espeak-ng provides a
# no-key local TTS fallback; a higher-quality OpenAI-compatible TTS can be
# enabled with TTS_API_KEY in production.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "bot.py"]
