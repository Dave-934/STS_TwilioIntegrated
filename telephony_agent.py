import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from livekit import api

from livekit.agents import AgentSession, Agent, RoomInputOptions, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, google, elevenlabs, silero
from livekit.plugins.turn_detector.english import EnglishModel

# Load env
dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger("telephony-agent")
logger.setLevel(logging.INFO)

OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")


class AssistantAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are Rachel, a helpful AI assistant from DL Interactive. "
                "Be polite, concise, and ask clarifying questions when needed."
            )
        )


async def entrypoint(ctx: JobContext):
    """
    Entrypoint run by livekit.agents.Worker. Handles STT, LLM, TTS, VAD, and publishing audio.
    """
    logger.info("Worker starting - connecting to room %s", ctx.room.name)
    await ctx.connect()

    # Outbound phone number to dial (from job metadata)
    phone_number_to_call = ctx.job.metadata

    # ----------------------
    # Plugin initialization
    # ----------------------
    stt = deepgram.STT(model="nova-2")
    llm = google.LLM(model="gemini-2.0-flash")
    tts = elevenlabs.TTS(
        voice_id=os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
        model="eleven_turbo_v2"
    )
    vad = silero.VAD.load()

    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        turn_detection=EnglishModel()
    )

    room_input_opts = RoomInputOptions()

    assistant = AssistantAgent()

    try:
        await session.start(room=ctx.room, agent=assistant, room_input_options=room_input_opts)
    except Exception:
        logger.exception("Failed to start AgentSession")
        raise

    # ----------------------
    # SIP Participant (dial out)
    # ----------------------
    logger.info("Attempting to dial %s ...", phone_number_to_call)
    try:
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=phone_number_to_call,
                participant_identity="phone-caller",
            )
        )
    except Exception:
        logger.exception(
            "Failed to create SIP participant (dial out). Continuing; session may still work."
        )

    # ----------------------
    # Generate initial greeting
    # ----------------------
    try:
        await session.generate_reply(
            instructions="Greet the user: 'Hello! This is Rachel from DL Interactive. How may I help you?'"
        )
    except Exception:
        logger.exception("Failed to generate initial greeting reply")

    # ----------------------
    # Keep the job running until room disconnect
    # ----------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="outbound-caller"))








