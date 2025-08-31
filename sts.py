import asyncio
import os
from dotenv import load_dotenv

from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.models.transcriber import PunctuationEndpointingConfig
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.output_device.blocking_speaker_output import BlockingSpeakerOutput
from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.streaming.models.audio import SamplingRate, AudioEncoding


load_dotenv()

async def main():
    microphone_input, speaker_output = create_streaming_microphone_input_and_speaker_output(
        use_default_devices=False,  # Set to True to use default input/output devices
        output_device_index=10  # Airdopes 141 (Headset) --> Replace with your headphones device index
        )

    transcriber = DeepgramTranscriber(
        DeepgramTranscriberConfig.from_input_device(
            microphone_input,
            endpointing_config=PunctuationEndpointingConfig(   # enables endpointing(VAD) based on punctuation or enables punctuation-based speech end detection.
                enabled=True,
                punctuation_marks=[".", "!", "?"],
                silence_duration_ms=1000,
                min_speech_duration_ms=1000,
                max_speech_duration_ms=10000,
            ),
            api_key=os.getenv("DEEPGRAM_API_KEY"),
            mute_during_speech=True,  # Add this line
        )
    )

    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            initial_message=BaseMessage(text="Hello! How can I help you today?"),
            prompt_preamble="You are a helpful conversational AI assistant."
        )
    )

    synthesizer_config = ElevenLabsSynthesizerConfig(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id="21m00Tcm4TlvDq8ikWAM",
        sampling_rate=SamplingRate.RATE_16000,      # for example, 16000 Hz
        audio_encoding=AudioEncoding.LINEAR16,       # example encoding
        output_device=speaker_output,
        stability=0.3,                               # value between 0 and 1 --> lower value for more natural voice
        similarity_boost=0.3                         # value between 0 and 1 --> lower value for less echo
    )
    synthesizer = ElevenLabsSynthesizer(synthesizer_config)
    synthesizer.words_per_minute = 150  # Set the speech rate to 110 WPM (the default speed is 150 WPM)

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=transcriber,
        agent=agent,
        synthesizer=synthesizer,
        speed_coefficient=0.2,  # Adjust: higher = faster response, lower = slower
    )

    await conversation.start()
    print("Conversation started! Press Ctrl+C to stop.")

    try:
        while conversation.is_active():
            chunk = await microphone_input.get_audio()
            conversation.receive_audio(chunk)
    except KeyboardInterrupt:
        await conversation.terminate()

if __name__ == "__main__":
    asyncio.run(main())
