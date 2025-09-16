import os
from dotenv import load_dotenv
from twilio.rest import Client
import time

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Get Twilio credentials from environment variables
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_NUMBER")
recipient_number = os.getenv("MY_PHONE_NUMBER")

# This is the public URL of your running RASA bot, provided by ngrok.
# IMPORTANT: This must be updated every time you restart ngrok.
# The URL points to the TwiML Bin which starts the media stream.
NGROK_URL = "wss://YOUR_CURRENT_NGROK_URL.ngrok.io" # Replace with your ngrok URL

# --- Main Script ---
if not all([account_sid, auth_token, twilio_number, recipient_number]):
    print("Error: Make sure all Twilio environment variables are set in your .env file.")
    exit()

if "YOUR_CURRENT_NGROK_URL" in NGROK_URL:
    print("Error: Please update the NGROK_URL variable in this script with your active ngrok forwarding URL.")
    exit()

# Initialize the Twilio client
client = Client(account_sid, auth_token)

# The URL of your TwiML Bin. Twilio will fetch instructions from here
# after it connects the call. This TwiML tells Twilio to open a <Stream>
# to your RASA bot's WebSocket.
twiml_url = f"{NGROK_URL.replace('wss://', 'https://')}/socket.io/?transport=websocket"

print("--- Initiating Outbound Call ---")
print(f"From: {twilio_number}")
print(f"To: {recipient_number}")
print(f"Connecting to RASA bot at: {NGROK_URL}")

try:
    # This is the API call that starts the outbound call
    call = client.calls.create(
        to=recipient_number,
        from_=twilio_number,
        twiml=f'<Response><Connect><Stream url="{NGROK_URL}/socket.io/?transport=websocket" /></Connect></Response>'
    )
    
    # Give a moment for the call to be initiated
    time.sleep(5) 
    
    # Fetch the call record to check its status
    call_record = client.calls(call.sid).fetch()
    print(f"Call initiated with SID: {call.sid}")
    print(f"Call status: {call_record.status}")
    print("Check your phone!")

except Exception as e:
    print(f"An error occurred: {e}")