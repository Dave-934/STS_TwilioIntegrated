# import os
# import queue
# import asyncio
# import logging
# import requests
# import sounddevice as sd
# import numpy as np
# from pydub import AudioSegment
# from io import BytesIO
# from deepgram import Deepgram
# from dotenv import load_dotenv
# import time

# # Load environment variables
# load_dotenv()

# # Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# # Constants
# SAMPLE_RATE = 16000
# CHANNELS = 1
# BLOCK_SIZE = 1024

# # API keys and endpoints from environment
# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"  # Replace with your Gemini endpoint
# ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
# ELEVENLABS_API_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

# # Initialize Deepgram client
# dg_client = Deepgram(DEEPGRAM_API_KEY)

# # Audio input queue
# q = queue.Queue()

# def audio_callback(indata, frames, time_info, status):
#     if status:
#         logging.warning(f"Sounddevice status: {status}")
#     q.put(indata.copy())

# async def deepgram_stream():
#     async with dg_client.transcription.live({
#         "punctuate": True,
#         "language": "en-US",
#         "vad": True,
#         "vad_sensitivity": 0.6,
#         "end_silence_timeout": 3.0
#     }) as dg_live:

#         async def send_audio():
#             while True:
#                 data = await loop.run_in_executor(None, q.get)
#                 await dg_live.send(data.tobytes())

#         send_task = asyncio.create_task(send_audio())

#         async for transcript in dg_live:
#             if transcript.get('channel', {}).get('alternatives'):
#                 utterance = transcript['channel']['alternatives'][0]['transcript'].strip()
#                 if utterance:
#                     yield utterance

#         await send_task

# def query_gemini(prompt_text):
#     headers = {
#         "Authorization": f"Bearer {GEMINI_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "prompt": prompt_text,
#         "max_tokens": 150,
#         "temperature": 0.7
#     }
#     response = requests.post(GEMINI_API_URL, headers=headers, json=payload)
#     response.raise_for_status()
#     data = response.json()
#     return data.get("text", "").strip()

# def elevenlabs_tts(text: str):
#     headers = {
#         "xi-api-key": ELEVENLABS_API_KEY,
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "text": text,
#         "voice_settings": {
#             "stability": 0.75,
#             "similarity_boost": 0.75
#         }
#     }
#     response = requests.post(ELEVENLABS_API_URL, headers=headers, json=payload)
#     response.raise_for_status()
#     audio_bytes = response.content
#     audio = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
#     return audio

# def play_audio_segment(audio: AudioSegment):
#     data = np.array(audio.get_array_of_samples())
#     sd.play(data, audio.frame_rate)
#     sd.wait()

# def start_audio_stream():
#     stream = sd.InputStream(
#         samplerate=SAMPLE_RATE,
#         channels=CHANNELS,
#         blocksize=BLOCK_SIZE,
#         callback=audio_callback
#     )
#     stream.start()
#     return stream

# async def main():
#     # Play welcome greeting
#     greeting = "Hello! How can I help you?"
#     logging.info("Playing greeting...")
#     audio = elevenlabs_tts(greeting)
#     play_audio_segment(audio)

#     stream = start_audio_stream()
#     global loop
#     loop = asyncio.get_running_loop()

#     try:
#         async for transcribed_text in deepgram_stream():
#             start_time_stt = time.time()
#             logging.info(f"STT Result: {transcribed_text}")

#             start_time_llm = time.time()
#             response_text = query_gemini(transcribed_text)
#             llm_time = time.time() - start_time_llm
#             logging.info(f"LLM Response: {response_text} (took {llm_time:.2f} s)")

#             start_time_tts = time.time()
#             audio_response = elevenlabs_tts(response_text)
#             tts_time = time.time() - start_time_tts

#             logging.info(f"TTS audio synthesized (took {tts_time:.2f} s)")
#             play_audio_segment(audio_response)

#             total_time = time.time() - start_time_stt
#             logging.info(f"Total roundtrip time: {total_time:.2f} s")

#             if not transcribed_text.strip():
#                 logging.info("Interruption detected via VAD: silence or speech cut-off")

#     except Exception as e:
#         logging.error(f"Pipeline error: {e}")
#     finally:
#         stream.stop()

# if __name__ == "__main__":
#     asyncio.run(main())












































import os
import logging
import requests
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from io import BytesIO
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from dotenv import load_dotenv
import threading
import queue
import time
import concurrent.futures

# Load environment variables
load_dotenv()

# Configure logging to show INFO and DEBUG messages
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024

# API keys and endpoints
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
ELEVENLABS_API_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

# Initialize Deepgram client
dg_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)

# Audio queue for streaming mic audio into Deepgram websocket
audio_q = queue.Queue()

# Event to signal streaming stop
stop_event = threading.Event()

# ThreadPoolExecutor for running blocking API calls async-friendly
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def audio_callback(indata, frames, time_info, status):
    if status:
        logging.warning(f"Sounddevice status: {status}")
    if not np.any(indata):
        logging.debug("Microphone silence detected")
    else:
        logging.debug(f"Microphone audio chunk received, shape: {indata.shape}")
    audio_q.put(indata.copy())

def query_gemini(prompt_text):
    headers = {
        "X-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ]
    }
    response = requests.post(GEMINI_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return data['candidates'][0]['content']['parts'][0]['text'].strip()

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

def stream_audio_to_deepgram(connection):
    while not stop_event.is_set():
        try:
            data = audio_q.get(timeout=0.1)
            connection.send(data.tobytes())
        except queue.Empty:
            continue
    connection.finish()

def process_transcript_and_respond(transcript):
    try:
        logging.info(f"[User]: {transcript}")

        # Query Gemini LLM
        start_time = time.time()
        response_text = query_gemini(transcript)
        duration = time.time() - start_time
        logging.info(f"[Bot]: {response_text} (LLM took {duration:.2f}s)")

        # Generate TTS audio
        start_time = time.time()
        audio_resp = elevenlabs_tts(response_text)
        duration = time.time() - start_time
        logging.info(f"TTS synthesized audio in {duration:.2f}s")

        # Play audio response
        play_audio_segment(audio_resp)

    except Exception as e:
        logging.error(f"Error in processing transcript or generating response: {e}")

def main():
    # Play initial greeting
    greeting = "Hello! How can I help you?"
    logging.info("Playing greeting...")
    audio = elevenlabs_tts(greeting)
    logging.info(f"Bot says: {greeting}")
    play_audio_segment(audio)

    # Create Deepgram websocket connection
    connection = dg_client.listen.websocket.v("1")

    # Transcript event handler
    def handle_transcript(event):
        transcript = event.channel.alternatives[0].transcript.strip()
        if not transcript:
            logging.info("Silence or no speech detected")
            return

        # Schedule LLM + TTS processing in executor to avoid blocking event thread
        executor.submit(process_transcript_and_respond, transcript)

    # Register transcript event callback
    connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)

    # Setup live options as per official example
    options = LiveOptions(
        model="nova-3",
        language="en-US",
        smart_format=True,
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        interim_results=True,
        utterance_end_ms="2000",
        vad_events=True,
        endpointing=300,
    )

    # Start the Deepgram connection
    connection.start(options)

    # Start the mic input stream
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        blocksize=BLOCK_SIZE,
        callback=audio_callback
    )
    stream.start()

    # Start background thread sending audio to Deepgram
    sender_thread = threading.Thread(target=stream_audio_to_deepgram, args=(connection,))
    sender_thread.daemon = True
    sender_thread.start()

    logging.info("Listening... Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(0.1)  # Keep main thread alive
    except KeyboardInterrupt:
        logging.info("Interrupted by user, shutting down...")
    finally:
        stop_event.set()
        stream.stop()
        sender_thread.join()
        logging.info("Cleaned up audio stream and websocket.")
        executor.shutdown(wait=True)

if __name__ == "__main__":
    main()
