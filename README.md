# STS_TwilioIntegrated

A Speech-to-Speech (STS) AI Voice Agent system with Twilio integration for real-time telephony conversations. This project enables natural voice interactions using LiveKit, OpenAI, and Twilio services.

## Overview

STS_TwilioIntegrated is a sophisticated voice AI agent that can engage in natural conversations through phone calls. The system leverages LiveKit's real-time communication framework, OpenAI's language models for intelligent responses, and Twilio for telephony integration. It supports both console-based testing and live phone call interactions.

## Features

- **Real-time Voice Conversations**: Seamless speech-to-speech interactions with low latency
- **Twilio Integration**: Make and receive phone calls through Twilio's telephony platform
- **OpenAI Integration**: Intelligent conversational AI powered by OpenAI's language models
- **LiveKit Framework**: Robust real-time communication infrastructure
- **Multiple Modes**: Console agent for testing and telephony agent for production calls
- **Docker Support**: Containerized deployment for easy setup and scalability
- **Flexible Configuration**: Environment-based configuration for different deployment scenarios

## Project Structure

```
STS_TwilioIntegrated/
├── console_agent.py          # Console-based voice agent for testing
├── telephony_agent.py        # Production telephony agent with Twilio integration
├── requirements.txt          # Python dependencies
├── Dockerfile               # Docker container configuration
├── docker-compose.yaml      # Docker Compose orchestration
├── .dockerignore           # Docker build exclusions
└── .gitignore              # Git version control exclusions
```

## Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose (for containerized deployment)
- LiveKit server instance
- Twilio account with phone number
- OpenAI API key

## Installation

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Dave-934/STS_TwilioIntegrated.git
   cd STS_TwilioIntegrated
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file in the project root with the following variables:
   ```env
   # LiveKit Configuration
   LIVEKIT_URL=wss://your-livekit-server.com
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   
   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key
   
   # Twilio Configuration (for telephony_agent.py)
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   ```

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Stop services**
   ```bash
   docker-compose down
   ```

## Usage

### Console Agent (Testing Mode)

The console agent allows you to test voice interactions locally without requiring phone integration:

```bash
python console_agent.py
```

This mode is ideal for:
- Development and debugging
- Testing conversation flows
- Validating AI responses
- Local demonstrations

### Telephony Agent (Production Mode)

The telephony agent handles live phone calls through Twilio:

```bash
python telephony_agent.py
```

This mode provides:
- Real phone call handling
- Inbound and outbound call support
- Production-grade voice interactions
- Twilio webhook integration

### Configuration Options

Both agents support various configuration options through environment variables:

- **Voice Settings**: Customize voice models and parameters
- **Language Models**: Configure OpenAI model selection and parameters
- **Audio Quality**: Adjust sampling rates and encoding
- **Logging**: Control verbosity and log output

## Dependencies

Key dependencies include:

- **livekit**: Real-time communication framework
- **livekit-agents**: Agent framework for LiveKit
- **livekit-plugins-openai**: OpenAI integration for LiveKit
- **livekit-plugins-silero**: Voice Activity Detection (VAD)
- **twilio**: Twilio API for telephony services
- **python-dotenv**: Environment variable management
- **aiohttp**: Async HTTP client/server

For a complete list, see `requirements.txt`.

## Architecture

### Console Agent
- Connects to LiveKit room for audio streaming
- Processes audio input from microphone
- Uses OpenAI for speech recognition and response generation
- Outputs synthesized speech to speakers

### Telephony Agent
- Receives incoming calls via Twilio webhooks
- Creates LiveKit room for each call session
- Bridges Twilio's media stream with LiveKit
- Processes voice interactions in real-time
- Handles call lifecycle events

## Development

### Running Tests

Start with the console agent for local testing:

```bash
python console_agent.py
```

### Code Structure

- **Agent Initialization**: Both scripts initialize LiveKit agents with necessary plugins
- **Event Handlers**: Define callbacks for connection, disconnection, and errors
- **Audio Processing**: Handle audio streams with appropriate codecs and processing
- **AI Integration**: Configure and manage OpenAI model interactions

### Debugging

Enable verbose logging by setting environment variables:

```bash
export LIVEKIT_LOG_LEVEL=debug
python console_agent.py
```

## Docker Configuration

### Dockerfile

The provided Dockerfile:
- Uses Python 3.9+ slim image
- Installs system dependencies for audio processing
- Copies application code and dependencies
- Configures runtime environment

### Docker Compose

The `docker-compose.yaml` file:
- Defines service configuration
- Manages environment variables
- Sets up networking
- Configures volume mounts

## Deployment

### Production Deployment

1. **Set up LiveKit server**: Deploy a LiveKit server instance (cloud or self-hosted)
2. **Configure Twilio**: 
   - Set up webhook URLs pointing to your telephony agent
   - Configure TwiML for call handling
3. **Deploy agent**: Use Docker Compose or your preferred container orchestration
4. **Monitor**: Set up logging and monitoring for production traffic

### Scaling

- Deploy multiple agent instances behind a load balancer
- Use Redis for session state management (if needed)
- Implement health checks and auto-scaling policies

## Contributing

Would love to have some amazing contributions! 

## Troubleshooting

### Common Issues

**Connection Issues**
- Verify LiveKit server URL and credentials
- Check network connectivity and firewall rules
- Ensure WebSocket connections are allowed

**Audio Problems**
- Verify microphone/speaker permissions
- Check audio device configuration
- Test audio codecs compatibility

**Twilio Integration**
- Validate webhook URLs are publicly accessible
- Check Twilio account credentials
- Review Twilio console logs for errors

**OpenAI API**
- Verify API key is valid and has sufficient credits
- Check rate limits and quota usage
- Review API error responses

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **LiveKit** for the real-time communication framework
- **OpenAI** for AI/ML capabilities
- **Twilio** for telephony services
- All contributors and maintainers

## Support

For questions, issues, or support:
- Open an issue on GitHub
- Check existing documentation and issues
- Review LiveKit and Twilio documentation

## Roadmap

Planned features and improvements:
- [ ] Multi-language support
- [ ] Enhanced error handling and recovery
- [ ] Call recording and transcription
- [ ] Advanced conversation analytics
- [ ] Custom voice training options
- [ ] Web dashboard for monitoring
- [ ] Kubernetes deployment templates

---

**Built with ❤️ by Dave-934**
