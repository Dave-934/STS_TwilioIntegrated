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

# Configure logging for normal operation
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Audio queue for playing back responses
playback_q = queue.Queue()

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
    # --- THIS IS THE FIX ---
    # Convert float32 audio from sounddevice to int16 for Deepgram
    int_data = (indata * 32767).astype(np.int16)
    audio_q.put(int_data.copy())

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

def playback_worker():
    logging.info("Playback thread started.")
    while not stop_event.is_set():
        try:
            audio_segment = playback_q.get(timeout=0.1)
            play_audio_segment(audio_segment)
            playback_q.task_done()
        except queue.Empty:
            continue
    logging.info("Playback thread stopped.")

def stream_audio_to_deepgram(connection):
    logging.info("Audio streaming thread started.")
    while not stop_event.is_set():
        try:
            data = audio_q.get(timeout=0.1)
            connection.send(data.tobytes())
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"Error sending audio to Deepgram: {e}")
    logging.info("Stopping audio streaming thread; calling connection.finish()")
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

        # --- CHANGE HERE ---
        # Put the audio in the playback queue instead of playing it directly
        playback_q.put(audio_resp)

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

    # Transcript event handler accepting the required 'result' argument
    def handle_transcript(self, result, **kwargs):
        try:
            if result.is_final and result.channel.alternatives[0].transcript:
                transcript = result.channel.alternatives[0].transcript.strip()

                # --- BARGE-IN LOGIC ---
                logging.info("User speech detected, stopping current playback.")
                sd.stop()  # Stop any currently playing audio
                # Clear the playback queue to prevent old responses from playing
                with playback_q.mutex:
                    playback_q.queue.clear()

                # Run Gemini + TTS responses on executor thread to avoid blocking
                executor.submit(process_transcript_and_respond, transcript)
        except Exception as ex:
            logging.error(f"Exception in transcript handler: {ex}")

    # Register transcript event callback
    connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)

    # Add handlers for connection lifecycle events to log them
    # Add handlers for connection lifecycle events to log them
    def on_open(self, open, **kwargs):
        logging.info("Deepgram websocket connection opened.")

    def on_close(self, close, **kwargs):
        logging.info("Deepgram websocket connection closed.")

    def on_error(self, error, **kwargs):
        logging.error(f"Deepgram connection error: {error}")

    connection.on(LiveTranscriptionEvents.Open, on_open)
    connection.on(LiveTranscriptionEvents.Close, on_close)
    connection.on(LiveTranscriptionEvents.Error, on_error)

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

    # Start the Deepgram websocket connection
    connection.start(options)

    # --- ADD THIS ---
    # Start the dedicated playback thread
    playback_thread = threading.Thread(target=playback_worker)
    playback_thread.daemon = True
    playback_thread.start()

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
        executor.shutdown(wait=True)
        logging.info("Cleaned up audio stream, threads, and websocket connection.")
        # Only finish connection now if not already finished
        try:
            connection.finish()
        except Exception as e:
            logging.debug(f"Websocket already finished or error on finish: {e}")

if __name__ == "__main__":
    main()
