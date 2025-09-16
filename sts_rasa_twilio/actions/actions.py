# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

import os
import requests
from typing import Any, Text, Dict, List
from dotenv import load_dotenv

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

# --- Load Environment Variables ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


# --- The Custom Action Class ---
class ActionAskGemini(Action):

    def name(self) -> Text:
        # This is the name we registered in domain.yml
        return "action_ask_gemini"

    def query_gemini(self, prompt_text: Text) -> Text:
        """
        Sends a prompt to the Google Gemini API and returns the text response.
        (This is your function, now part of the class)
        """
        headers = {
            "X-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

        try:
            response = requests.post(GEMINI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            print(f"An error occurred calling Gemini API: {e}")
            return "I'm sorry, I'm having trouble thinking right now. Please try again later."

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Get the user's last message
        user_message = tracker.latest_message.get('text')

        print(f"User message received by action: {user_message}")

        # Call the Gemini API
        response_text = self.query_gemini(user_message)

        # Send the response back to the user
        dispatcher.utter_message(text=response_text)

        return []