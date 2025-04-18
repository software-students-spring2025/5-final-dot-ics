from icalendar import Calendar, Event
from datetime import datetime, timedelta
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import google.generativeai as genai
import os
import json
import re

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DBNAME")
client = MongoClient(mongo_uri)
db = client[db_name]
events_collection = db["events"]

key=os.getenv("GOOGLE_API_KEY")
# Authenticate
genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.0-flash")

event_schema = {
    "event_name": "string (name of the event)",
    "date": "string (format: YYYY-MM-DD, e.g. 2025-04-30)",
    "time": "string (optional, e.g. 14:00 PM)",
    "location": "string (where the event is happening)",
    "description": "string (optional, a short summary of the event)"
}

class ICSClient:
    def __init__(self):
        pass

    def parse_text_to_event_data(self, text: str) -> dict:
            prompt = f"""
        Extract event title, date in format YYYY-MM-DD, time, location, and implied description from the following text. Respond only in JSON format. 
        Recognize that users may use shorthand to denote things, such as 'tmr' denoting 'tomorrow', and things of that nature. 
        Also, recognize the difference between "this ..." and "next ...", with the weeks starting on Sunday and ending on Saturday.

        Schema:
        {json.dumps(event_schema, indent=2)}

        Text:
        {text}
        """

            response = model.generate_content(prompt)
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    print("Failed to parse JSON:\n", response.text)
            else:
                print("No JSON detected:\n", response.text)

            return None
        
        # return {
        #     "name": "Dinner with Family",
        #     "start": datetime(2025, 4, 18, 14, 0, 0),
        #     "end": datetime(2025, 4, 18, 15, 0, 0),
        #     "description": f"User Input: {text}\nLLM Understanding: Dinner with family at home from ___ to ___.",
        #     "location": "Home"
        # }

    def store_event(self, event_data, ics_file_path):
        event_data["created_at"] = datetime.now()

        result = events_collection.insert_one(event_data)
        print(f"Event stored in MongoDB with ID: {result.inserted_id}")

        with open(ics_file_path, 'rb') as ics_file:
            ics_content = ics_file.read()
            events_collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"ics_file": ics_content}}
            )
        print(f".ICS stored in MongoDB with ID: {result.inserted_id}")

    def create_event(self, text: str) -> str:
        event_data = self.parse_text_to_event_data(text)

        cal = Calendar()
        event = Event()

        # event.add("user", )
        event.add("summary", event_data["name"])
        event.add("dtstart", event_data["start"])
        event.add("dtend", event_data["end"])
        event.add("description", event_data["description"])
        event.add("location", event_data["location"])
        event.add("uid", str(uuid.uuid4()))
        event.add("dtstamp", datetime.now())

        cal.add_component(event)

        ics_path = Path("./events/event.ics")
        with open(ics_path, "wb") as f:
            f.write(cal.to_ical())

        self.store_event(event_data, ics_path)

if __name__ == "__main__":
    client = ICSClient()
    text_input = "Friday dinner with fam at home"   # to be replaced w/ text from web-app.
    ics_file_path = client.create_event(text_input)
    print(f".ICS file created.")

    # Testing LLM
    sample_text = """
     Group project meeting next Fri 10pm in the conference room located at the Silver Building.
    """
    event = client.parse_text_to_event_data(sample_text)
    print("Prompt: ", sample_text)
    print(json.dumps(event, indent=2) if event else "No event extracted.")