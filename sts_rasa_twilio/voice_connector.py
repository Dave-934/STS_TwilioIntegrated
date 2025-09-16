import os
import logging
import asyncio
from fastapi import FastAPI
from rasa.core.channels.socketio import SocketIOInput
from rasa.core.agent import Agent
from dotenv import load_dotenv
import socketio
from typing import Text, Dict, Any, Optional, Callable, Awaitable

# --- NEW IMPORTS FOR VOICE PROCESSING ---
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
import websocket
import json
import base64

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
load_dotenv()
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

# --- WEB SERVER SETUP ---
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, app)

class VoiceInput(SocketIOInput):
    """A custom input channel that handles real-time audio streams."""

    @classmethod
    def name(cls) -> Text:
        return "voice_connector"

    def __init__(self,
                 agent: "Agent",
                 sio: "socketio.AsyncServer",
                 bot_message_evt: Text = "bot_uttered",
                 namespace: Optional[Text] = None,
                 ):
        self.agent = agent
        # Note: We use custom event names for clarity
        super().__init__(sio, bot_message_evt, "user_audio_chunk", namespace)

    def blueprint(
        self, on_new_message: Callable[[Dict[Text, Any]], Awaitable[None]]
    ) -> "socketio.ASGIApp":
        
        # Dictionary to hold a Deepgram connection for each user session
        self.dg_connections = {}

        @self.sio.on("connect", namespace=self.namespace)
        async def connect(sid: Text, environ: Dict):
            logger.info(f"New client connected: {sid}")
            
            # --- SETUP DEEPGRAM CONNECTION ON CONNECT ---
            try:
                dg_client = DeepgramClient(DEEPGRAM_API_KEY)
                connection = dg_client.listen.websocket.v("1")
                self.dg_connections[sid] = connection

                async def handle_transcript(self, result, **kwargs):
                    if result.is_final and result.channel.alternatives[0].transcript:
                        transcript = result.channel.alternatives[0].transcript.strip()
                        logger.info(f"Final transcript from {sid}: {transcript}")
                        
                        user_message = {
                            "sender_id": sid,
                            "text": transcript,
                            "input_channel": self.name(),
                            "metadata": {}
                        }
                        await on_new_message(user_message)

                connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)

                options = LiveOptions(
                    model="nova-2", language="en-US", encoding="mulaw", sample_rate=8000,
                    interim_results=False, utterance_end_ms="1000", vad_events=True
                )
                await connection.start(options)
                logger.info(f"Deepgram connection started for {sid}")

            except Exception as e:
                logger.error(f"Error starting Deepgram for {sid}: {e}")

        @self.sio.on(self.user_message_evt, namespace=self.namespace)
        async def handle_audio_chunk(sid: Text, data: bytes):
            """Handle incoming audio chunks from the client."""
            connection = self.dg_connections.get(sid)
            if connection:
                await connection.send(data)

        @self.sio.on("disconnect", namespace=self.namespace)
        async def disconnect(sid: Text):
            logger.info(f"Client disconnected: {sid}")
            connection = self.dg_connections.pop(sid, None)
            if connection:
                await connection.finish()
                logger.info(f"Deepgram connection closed for {sid}")

        return socket_app

    async def send(self, payload: Dict[Text, Any], **kwargs: Any) -> None:
        """This is called by Rasa when the bot wants to send a message."""
        sid = payload.get("sender_id")
        message = payload.get("text")
        
        if not message:
            return

        logger.info(f"Sending message to {sid}: {message}")
        
        # --- TTS STREAMING LOGIC ---
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream-input?model_id=eleven_turbo_v2"
        ws = websocket.create_connection(uri)
        
        auth_payload = {"xi_api_key": ELEVENLABS_API_KEY}
        ws.send(json.dumps(auth_payload))
        
        text_payload = {"text": message, "try_trigger_generation": True}
        ws.send(json.dumps(text_payload))
        
        ws.send(json.dumps({}))

        while True:
            try:
                data = ws.recv()
                message_data = json.loads(data)
                if message_data.get("audio"):
                    audio_chunk = base64.b64decode(message_data["audio"])
                    if audio_chunk:
                        # Emit audio chunk back to the client (Twilio)
                        await self.sio.emit("bot_audio_chunk", audio_chunk, room=sid)
                elif message_data.get("isFinal"):
                    break
            except websocket.WebSocketConnectionClosedException:
                break
        
        logger.info(f"Finished streaming TTS for {sid}")