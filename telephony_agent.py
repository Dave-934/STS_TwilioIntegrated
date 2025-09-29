import asyncio
import logging
from dotenv import load_dotenv
import json
import os
from pathlib import Path # <--- CHANGE: Added pathlib for robust .env loading
from time import perf_counter
from typing import Annotated

from livekit import rtc, api
from livekit.agents import JobContext, JobProcess, WorkerOptions, cli, llm
from livekit.agents.utils import AudioBuffer # <--- CHANGE: Added necessary import
from livekit.plugins import deepgram, google, elevenlabs, silero # <--- CHANGE: Corrected google import

# Using pathlib for the most reliable .env loading
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")

async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()

    phone_number_to_call = ctx.job.metadata

    # --- CHANGE: Corrected variable assignments ---
    # Each plugin must be assigned to its own variable on a separate line.
    stt = deepgram.STT(model="nova-2") # Using stable model
    llm = google.LLM(model="gemini-2.0-flash") # Using stable model
    tts = elevenlabs.TTS(voice_id="21m00Tcm4TlvDq8ikWAM", model="eleven_turbo_v2") # Using stable model
    vad = silero.VAD.load()
    # --- END OF CHANGE ---

    # This line will now work correctly
    source = rtc.AudioSource(tts.sample_rate, tts.num_channels)
    track = rtc.LocalAudioTrack.create_audio_track("agent-mic", source)
    await ctx.room.local_participant.publish_track(track)


    async def handle_speech(participant: rtc.RemoteParticipant):
        logger.info(f"Participant {participant.identity} connected, starting conversation.")
        
        stt_stream = stt.stream()
        
        # <--- FIX : Correctly find the audio track for your library version ---
        audio_stream = None
        for track_pub in participant.track_publications.values():
            if track_pub.track and track_pub.kind == rtc.TrackKind.AUDIO:
                # Wait for the track to be available
                while track_pub.track is None:
                    await asyncio.sleep(0.1)
                audio_stream = rtc.AudioStream(track_pub.track)
                break
        
        if audio_stream is None:
            logger.error("Could not find an audio track for the participant")
            return

        vad_stream = vad.stream(audio_stream)
        tts_stream = tts.stream()
        
        async def play_tts_audio():
            async for audio_frame in tts_stream:
                await source.capture_frame(audio_frame)

        tts_playback_task = asyncio.create_task(play_tts_audio())

        # <--- FIX : Corrected chat context handling ---
        # Create the chat object once to maintain conversation history
        chat = llm.chat()
        chat.messages.append(llm.ChatMessage(role=llm.ChatRole.SYSTEM, text="You are a helpful AI assistant named Rachel from DL Interactive."))
        
        # This is a "fake" user message to kickstart the conversation for the greeting
        chat.messages.append(llm.ChatMessage(role=llm.ChatRole.USER, text="The call has just connected. Greet the user by saying 'Hello! This is Rachel from DL Interactive, How may I help you ?'"))
        
        llm_stream = await chat.stream()
        async for chunk in llm_stream:
            if chunk.delta.content:
                tts_stream.push_text(chunk.delta.content)
        
        await tts_stream.flush()

        # Main conversation loop
        while True:
            user_speech = AudioBuffer()
            async for event in vad_stream:
                if event.type == silero.VAD.Event.Type.FRAME:
                    user_speech.push(event.frame)
                elif event.type == silero.VAD.Event.Type.SPEAKING_ENDED:
                    break
            
            if not user_speech:
                continue

            stt_stream.push_buffer(user_speech)
            result = await stt_stream.flush()
            if not result or not result.alternatives:
                continue
            
            transcript = result.alternatives[0].transcript
            logger.info(f"User said: {transcript}")

            # Append the user's new message to the existing chat
            chat.messages.append(llm.ChatMessage(role=llm.ChatRole.USER, text=transcript))
            
            llm_stream_result = await chat.stream()
            async for chunk in llm_stream_result:
                if chunk.delta.content:
                    tts_stream.push_text(chunk.delta.content)
            
            await tts_stream.flush()


    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        if participant.identity == "phone-caller":
            asyncio.create_task(handle_speech(participant))

    logger.info(f"Attempting to dial {phone_number_to_call}...")
    try:
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=phone_number_to_call,
                participant_identity="phone-caller",
            )
        )
    except Exception as e:
        logger.error(f"Error creating SIP participant: {e}")
        ctx.shutdown()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )









# import asyncio
# import logging
# from dotenv import load_dotenv
# import os
# from pathlib import Path

# from livekit import rtc, api
# from livekit.agents import JobContext, WorkerOptions, cli, llm
# from livekit.agents.utils import AudioBuffer
# from livekit.plugins import deepgram, google, elevenlabs, silero

# dotenv_path = Path(__file__).resolve().parent / '.env'
# load_dotenv(dotenv_path=dotenv_path)

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger("telephony-agent")

# OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")

# async def entrypoint(ctx: JobContext):
#     phone_number_to_call = ctx.job.metadata

#     # Connect to the room
#     await ctx.connect()
#     logger.info(f"Agent connected to room {ctx.room.name}")

#     # Create the pipeline components
#     stt=deepgram.STT(
#             api_key=os.getenv("DEEPGRAM_API_KEY"),
#             model="nova-3",
#             language="en"
#             ),
#     llm=google.LLM(
#             api_key=os.getenv("GEMINI_API_KEY"),
#             model="gemini-2.0-flash"
#             ),
#     tts=elevenlabs.TTS(
#             api_key=os.getenv("ELEVENLABS_API_KEY"),
#             voice_id="21m00Tcm4TlvDq8ikWAM",
#             model="eleven_turbo_v2"
#             ),
#     vad = silero.VAD.load()

#     # Create the agent's audio track to send audio
#     source = rtc.AudioSource(tts.sample_rate, tts.num_channels)
#     track = rtc.LocalAudioTrack.create_audio_track("agent-mic", source)
#     await ctx.room.local_participant.publish_track(track)

#     async def handle_speech(participant: rtc.RemoteParticipant):
#         logger.info(f"Participant {participant.identity} connected, starting conversation.")
        
#         # Setup streams
#         stt_stream = stt.stream()
#         vad_stream = vad.stream(rtc.AudioStream(participant.get_track_publication_by_name("mic-track-0").track))
#         tts_stream = tts.stream()
        
#         # Forward TTS audio to the agent's audio track
#         async def play_tts_audio():
#             async for audio_frame in tts_stream:
#                 await source.capture_frame(audio_frame)

#         tts_playback_task = asyncio.create_task(play_tts_audio())

#         # Main conversation loop
#         while True:
#             # Wait for user to finish speaking
#             user_speech = AudioBuffer()
#             async for event in vad_stream:
#                 if event.type == silero.VAD.Event.Type.FRAME:
#                     user_speech.push(event.frame)
#                 elif event.type == silero.VAD.Event.Type.SPEAKING_ENDED:
#                     break
            
#             if not user_speech:
#                 continue

#             # Transcribe user speech
#             stt_stream.push_buffer(user_speech)
#             result = await stt_stream.flush()
#             if not result or not result.alternatives:
#                 continue
            
#             transcript = result.alternatives[0].transcript
#             logger.info(f"User said: {transcript}")

#             # Get LLM response
#             chat = llm.chat()
#             chat.messages.append(llm.ChatMessage(role=llm.ChatRole.SYSTEM, text="You are a helpful AI assistant."))
#             chat.messages.append(llm.ChatMessage(role=llm.ChatRole.USER, text=transcript))
            
#             llm_stream = await chat.stream()
#             async for chunk in llm_stream:
#                 if chunk.delta.content:
#                     tts_stream.push_text(chunk.delta.content)
            
#             await tts_stream.flush()

#     @ctx.room.on("participant_connected")
#     def on_participant_connected(participant: rtc.RemoteParticipant):
#         asyncio.create_task(handle_speech(participant))

#     logger.info(f"Attempting to dial {phone_number_to_call}...")
#     try:
#         await ctx.api.sip.create_sip_participant(
#             api.CreateSIPParticipantRequest(
#                 room_name=ctx.room.name,
#                 sip_trunk_id=OUTBOUND_TRUNK_ID,
#                 sip_call_to=phone_number_to_call,
#                 participant_identity="phone-caller",
#             )
#         )
#     except Exception as e:
#         logger.error(f"Error creating SIP participant: {e}")
#         ctx.shutdown()


# if __name__ == "__main__":
#     cli.run_app(
#         WorkerOptions(
#             entrypoint_fnc=entrypoint,
#             agent_name="outbound-caller",
#         )
#     )














# import asyncio
# import logging
# from dotenv import load_dotenv
# import os
# from pathlib import Path  

# from livekit import rtc, api
# from livekit.agents import JobContext, WorkerOptions, cli
# from livekit.agents.voice import Agent, AgentSession
# from livekit.plugins import google, elevenlabs, deepgram, silero
# from livekit.plugins.turn_detector.english import EnglishModel


# dotenv_path = Path(__file__).resolve().parent / '.env'
# load_dotenv(dotenv_path=dotenv_path)

# logger = logging.getLogger("outbound-caller")
# logger.setLevel(logging.INFO)

# OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")

# class TelemarketerAgent(Agent):
#     def __init__(self, customer_name: str, product_name: str):
#         super().__init__(
#             instructions=f"""
#             You are a highly enthusiastic and persuasive telemarketer for 'Starlight Subscriptions'.
#             Your goal is to convince the user to sign up for a free one-month trial of our premium service.
#             You are friendly, energetic, and refuse to take no for an answer easily, but you are never rude.
#             The customer's name is {customer_name}. The product is our '{product_name}' package.
#             Be creative and engaging.
#             """,
#             stt=deepgram.STT(
#             api_key=os.getenv("DEEPGRAM_API_KEY"),
#             model="nova-3",
#             language="en"
#             ),
#             llm=google.LLM(
#             api_key=os.getenv("GEMINI_API_KEY"),
#             model="gemini-2.0-flash"
#             ),
#             tts=elevenlabs.TTS(
#             api_key=os.getenv("ELEVENLABS_API_KEY"),
#             voice_id="21m00Tcm4TlvDq8ikWAM",
#             model="eleven_turbo_v2"
#             ),
#             vad=silero.VAD.load(),
#         )
    
#     async def on_enter(self):
#         await self.session.generate_reply(
#             instructions="Start the call with an energetic opening line. Greet the customer by name and introduce yourself from 'Starlight Subscriptions' with an amazing, limited-time offer."
#         )

# async def entrypoint(ctx: JobContext):
#     phone_number_to_call = ctx.job.metadata

#     agent = TelemarketerAgent(
#         customer_name="Divyansh",
#         product_name="Galactic Explorer",
#     )

#     session = AgentSession(
#         turn_detection=EnglishModel(),
#     )

#     logger.info(f"Attempting to dial {phone_number_to_call}...")
#     try:
#         await ctx.api.sip.create_sip_participant(
#             api.CreateSIPParticipantRequest(
#                 room_name=ctx.room.name,
#                 sip_trunk_id=OUTBOUND_TRUNK_ID,
#                 sip_call_to=phone_number_to_call,
#                 participant_identity="phone-caller",
#                 wait_until_answered=True,
#             )
#         )
#     except Exception as e:
#         logger.error(f"Error dialing number: {e}")
#         ctx.shutdown()
#         return

#     logger.info("Call connected, starting agent session.")
#     await session.start(agent=agent, room=ctx.room)

# if __name__ == "__main__":
#     cli.run_app(
#         WorkerOptions(
#             entrypoint_fnc=entrypoint,
#             agent_name="outbound-caller",
#             # --- THIS IS THE FINAL FIX ---
#             # This tells the agent to run in a single process, avoiding the
#             # inter-process communication bug that was causing the timeout.
#             num_inference_procs=0
#         )
#     )