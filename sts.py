import os
import queue
import asyncio
import logging
import requests
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from io import BytesIO
from deepgram import Deepgram
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024

# API keys and endpoints from environment
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://gemini.api.url/v1/generate"  # Replace with your Gemini endpoint
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
ELEVENLABS_API_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

# Initialize Deepgram client
dg_client = Deepgram(DEEPGRAM_API_KEY)

# Audio input queue
q = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status:
        logging.warning(f"Sounddevice status: {status}")
    q.put(indata.copy())

async def deepgram_stream():
    async with dg_client.transcription.live({
        "punctuate": True,
        "language": "en-US",
        "vad": True,
        "vad_sensitivity": 0.6,
        "end_silence_timeout": 3.0
    }) as dg_live:

        async def send_audio():
            while True:
                data = await loop.run_in_executor(None, q.get)
                await dg_live.send(data.tobytes())

        send_task = asyncio.create_task(send_audio())

        async for transcript in dg_live:
            if transcript.get('channel', {}).get('alternatives'):
                utterance = transcript['channel']['alternatives'][0]['transcript'].strip()
                if utterance:
                    yield utterance

        await send_task

def query_gemini(prompt_text):
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt_text,
        "max_tokens": 150,
        "temperature": 0.7
    }
    response = requests.post(GEMINI_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return data.get("text", "").strip()

def elevenlabs_tts(text: str):
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75
        }
    }
    response = requests.post(ELEVENLABS_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    audio_bytes = response.content
    audio = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
    return audio

def play_audio_segment(audio: AudioSegment):
    data = np.array(audio.get_array_of_samples())
    sd.play(data, audio.frame_rate)
    sd.wait()

def start_audio_stream():
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        blocksize=BLOCK_SIZE,
        callback=audio_callback
    )
    stream.start()
    return stream

async def main():
    # Play welcome greeting
    greeting = "Hello! How can I help you?"
    logging.info("Playing greeting...")
    audio = elevenlabs_tts(greeting)
    play_audio_segment(audio)

    stream = start_audio_stream()
    global loop
    loop = asyncio.get_running_loop()

    try:
        async for transcribed_text in deepgram_stream():
            start_time_stt = time.time()
            logging.info(f"STT Result: {transcribed_text}")

            start_time_llm = time.time()
            response_text = query_gemini(transcribed_text)
            llm_time = time.time() - start_time_llm
            logging.info(f"LLM Response: {response_text} (took {llm_time:.2f} s)")

            start_time_tts = time.time()
            audio_response = elevenlabs_tts(response_text)
            tts_time = time.time() - start_time_tts

            logging.info(f"TTS audio synthesized (took {tts_time:.2f} s)")
            play_audio_segment(audio_response)

            total_time = time.time() - start_time_stt
            logging.info(f"Total roundtrip time: {total_time:.2f} s")

            if not transcribed_text.strip():
                logging.info("Interruption detected via VAD: silence or speech cut-off")

    except Exception as e:
        logging.error(f"Pipeline error: {e}")
    finally:
        stream.stop()

if __name__ == "__main__":
    asyncio.run(main())
