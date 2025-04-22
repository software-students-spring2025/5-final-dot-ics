"""
ICS Client module.
Module is responsible for parsing user input,
generating the ICS event and storing it in the MongoDB.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import uuid
import json
import re
from icalendar import Calendar, Event
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DBNAME")

key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.0-flash")


class ICSClient:
    """
    Class for the ICS generation client.
    """

    def __init__(self):
        try:
            self.client = MongoClient(mongo_uri)
            self.client.server_info()
            self.db = self.client[db_name]
            self.events_collection = self.db["events"]
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise Exception(f"MongoDB connection failed: {e}")

    def create_dt_object(self, date_str, time_str):
        """
        create_dt_object creates a date time object.
        Method returns the object.
        """
        if date_str in ("None", "null", "", None):
            return None

        year, month, day = map(int, date_str.split("-"))
        hour, minute = 0, 0

        if time_str not in ("None", "null", "", None):
            hour, minute = map(int, time_str.split(":"))

        return datetime(
            year, month, day, hour, minute, 0, tzinfo=ZoneInfo("America/New_York")
        )

    def parse_text_to_event_data(self, text: str) -> dict:
        """
        parse_text_to_event_data parses input and generates data for creating the ICS file.
        Returns event data, or error on error.
        """
        eastern_now = datetime.now(ZoneInfo("America/New_York"))
        today_str = eastern_now.strftime("%Y/%m/%d")
        print("Today's date (ET):", today_str)

        prompt = f"""
        Extract:
        event title, 
        date (calculate calendar date from {today_str}, treat the word "next" or "nxt" as next week),
        start time, 
        end time, 
        location, 
        and implied description from the following text. 
        Respond only in JSON format.

        Schema:
        {{
        "name": "string (event title)",
        "date": "string (format: YYYY-MM-DD)",
        "start_time": "string (optional, format: HH:MM in 24-hour time)",
        "end_time": "string (optional, format: HH:MM in 24-hour time)",
        "location": "string",
        "description": "string (optional)"
        }}

        Text:
        {text}
        """

        response = model.generate_content(prompt)

        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not match:
            print("No JSON detected in response.")
            return {"error": "No valid event extracted"}

        try:
            event_data = json.loads(match.group(0))
            print("Parsed event data:", event_data)
            start_dt = self.create_dt_object(
                event_data["date"], event_data.get("start_time")
            )
            end_dt = self.create_dt_object(
                event_data["date"], event_data.get("end_time")
            )

            return {
                "name": event_data.get("name"),
                "start": start_dt,
                "end": end_dt,
                "location": event_data.get("location"),
                "description": event_data.get("description"),
            }

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print("Failed to parse event JSON:", e)
            return {"error": "Invalid event format"}

    def store_event(self, event_data, ics_file_path):
        """
        store_event method stores the event object in the MongoDB.
        Method does not return.
        """
        event_data["created_at"] = datetime.now()

        result = self.events_collection.insert_one(event_data)
        print(f"Event stored in MongoDB with ID: {result.inserted_id}")

        with open(ics_file_path, "rb") as ics_file:
            ics_content = ics_file.read()
            self.events_collection.update_one(
                {"_id": result.inserted_id}, {"$set": {"ics_file": ics_content}}
            )
        print(f".ICS stored in MongoDB with ID: {result.inserted_id}")

    def create_event(self, text: str) -> str:
        """
        create_event method creates the event object.
        Method returns the path to the locally stored ics file.
        """
        event_data = self.parse_text_to_event_data(text)

        if "error" in event_data:
            raise ValueError(f"Failed to parse event: {event_data['error']}")

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

        return str(ics_path)


if __name__ == "__main__":
    client = ICSClient()
    TEXT_INPUT = (
        "Friday dinner with fam at home"  # to be replaced w/ text from web-app.
    )
    ICS_FILE_PATH = client.create_event(TEXT_INPUT)
    print(".ICS file created.")

    # Run sample prompts
    samples = [
        "Brunch w/ Sarah next Sunday, 11am @ the Garden Cafe. To discuss the upcoming wedding.",
        "Group project meeting tmr at 10 at night in  Silver Building conference room.",
        "project meeting, for flask web app, 2-3 next Sat Bobst Library rm 903",
        "Meeting abt class registration, from 9 for 2.5 hrs, next Sat Bobst Library rm 903",
    ]

    for i, sample_text in enumerate(samples, 1):
        print(f"\nPrompt {i}: {sample_text.strip()}")
        event = client.parse_text_to_event_data(sample_text)
        print(
            json.dumps(event, indent=2, default=str) if event else "No event extracted."
        )
