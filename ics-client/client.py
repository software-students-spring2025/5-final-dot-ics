"""
ICS Client module.
Module is responsible for parsing user input,
generating the ICS event and storing it in the MongoDB.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import uuid
import json
import re
from icalendar import Calendar, Event
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from google import genai
from flask import Flask, request, jsonify

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DBNAME")
client = MongoClient(mongo_uri)
db = client[db_name]
events_collection = db["events"]

# Configure Gemini model
key = os.getenv("GOOGLE_API_KEY")
genai_client = genai.Client(api_key=key)


class ICSClient:
    """
    Class for the ICS generation client.
    """

    def __init__(self):
        pass

    def create_dt_object(self, date_str, time_str):
        """
        create_dt_object creates a date time object.
        Method returns the object.
        """
        if date_str in ("None", "null", "", None):
            date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

        year, month, day = map(int, date_str.split("-"))

        if time_str not in ("None", "null", "", None):
            hour, minute = map(int, time_str.split(":"))

            return datetime(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                tzinfo=ZoneInfo("America/New_York")
            )
        
        return date(year=year, month=month, day=day)

    def parse_text_to_event_data(self, text: str) -> dict:
        """
        parse_text_to_event_data parses input and generates data for creating the ICS file.
        Returns event data, or error.
        """
        eastern_now = datetime.now(ZoneInfo("America/New_York"))
        today_str = eastern_now.strftime("%Y-%m-%d")
        app.logger.debug("*** Today's date: %s", today_str)

        prompt = f"""
        Extract event title, date (calculate calendar date from {today_str}, treat the word "next" or "nxt" as 
        "next week", treat the word "tmr" as "tomorrow"), time, location, and implied description from: {text}

        Respond only in JSON format using the following schema.

        Schema:
        {{
        "name": "string (event title, null if event title is not provided)",
        "date": "string (null if date time is not provided, format: YYYY-MM-DD)",
        "start_time": "string (null if start time is not provided, format: HH:MM in 24-hour time)",
        "end_time": "string (null if end time is not provided, format: HH:MM in 24-hour time)",
        "location": "string (null if location is not provided)",
        "description": "string (null if description cannot be inferred)"
        }}
        """
        app.logger.debug("**** Prompt: %s", prompt)
        response = genai_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        app.logger.debug("**** Input Text: %s", text)
        app.logger.debug("**** Gemini Response Type: %s", type(response.text))
        app.logger.debug("**** Gemini Response: %s", response.text)
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not match:
            print("No JSON detected in response.")
            return {"error": "No valid event extracted", "error_code": 401}

        try:
            event_data = json.loads(match.group(0))
            app.logger.debug("***Parsed event data: %s", json.dumps(event_data, indent=2))
            date = event_data["date"]
            start_time = event_data.get("start_time")
            app.logger.debug("**** date= %s, start_time= %s", date, start_time)
            start_dt = self.create_dt_object(date, start_time)

            end_time = event_data.get("end_time")
            end_dt = None
            if end_time:
                end_dt = self.create_dt_object(date, end_time)

                if end_dt and start_dt and isinstance(start_dt, datetime) and isinstance(end_dt, datetime):
                    if end_dt < start_dt:
                        return {"error": "End time cannot be before start time.", "error_code": 402}

            result = {
                "name": event_data.get("name"),
                "start": start_dt,
                "end": end_dt,
                "location": event_data.get("location"),
                "description": event_data.get("description"),
            }
            app.logger.debug("***Result dict: %s", result)
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print("Failed to parse event JSON:", e)
            return {"error": "Invalid event format", "error_code": 403}

    def format_event_data(self, data):
        """
        Formats each value in the event data dictionary as a string for database storage.
        """
        str_event_data = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                str_event_data[key] = value.strftime("%b %d, %Y %l:%M%p")
            elif isinstance(value, date):
                str_event_data[key] = value.strftime("%b %d, %Y")
            else:
                str_event_data[key] = value

        # Default event name to "New Event" if none is provided
        if not str_event_data.get("name"):
            str_event_data["name"] = "New Event"

        return str_event_data

    def store_event(self, entry_id, event_data, ics_file_path):
        """
        store_event method stores the event object in the MongoDB.
        Method does not return.
        """

        with open(ics_file_path, "rb") as ics_file:
            ics_content = ics_file.read()
            events_collection.update_one(
                {"_id": ObjectId(entry_id)},
                {
                    "$set": {
                        "event_data": self.format_event_data(event_data),
                        "ics_file": ics_content,
                        "ics_file_path": str(ics_file_path),
                    }
                }
            )
        print(f".ICS stored in MongoDB with ID: {entry_id}")

    def create_event(self, entry_id: str) -> bool:
        """
        create_event method creates the event object from an entry in the database.
        Returns:
            tuple: (bool, error dict)
            bool is True if the .ics file was created and stored successfully, False if the entry has no text.
        """
        doc = events_collection.find_one({"_id": ObjectId(entry_id)}, {"text": 1})
        text = doc.get("text")

        if not text:
            return (False, {"error": "No text found in the entry.", "error_code": 421})
        
        app.logger.debug("*** create_event(): Found entry_text: %s", text)
        event_data = self.parse_text_to_event_data(text)

        if "error" in event_data:
            return (False, event_data)

        cal = Calendar()
        event = Event()

        summary = event_data["name"]
        if summary is not None:
            event.add("summary", summary)
        else:
            event.add("summary", "New Event")
        start = event_data["start"]
        if start is not None:
            event.add("dtstart", start)
        end = event_data["end"]
        if end is not None:
            event.add("dtend", end)
        desc = event_data["description"]
        if desc is not None:
            event.add("description", event_data["description"])
        loc = event_data["location"]
        if loc is not None:
            event.add("location", loc)
        event.add("uid", str(uuid.uuid4()))
        event.add("dtstamp", datetime.now(ZoneInfo("America/New_York")))

        cal.add_component(event)

        ics_path = Path(f"./events/{entry_id}.ics")
        app.logger.debug("*** create_event(): ics_path=%s", ics_path)

        # Check if /events folder is created. If not, create one
        ics_path.parent.mkdir(parents=True, exist_ok=True)
        app.logger.debug("Current working directory: %s", os.getcwd())
        with open(ics_path, "wb") as f:
            f.write(cal.to_ical())
            app.logger.debug("*** create_event(): event saved to file")

        self.store_event(entry_id, event_data, ics_path)
        return (True, None)

app = Flask(__name__)
ics_client = ICSClient()

@app.route("/run-client", methods=["POST"])
def process_request():
    """
    Handle POST requests to generate an ICS event based on saved user input. 
    Returns:
        JSON response with a status message and the updated entry_id.
        Returns HTTP 400 if `entry_id` is missing.
    """

    data = request.get_json()
    entry_id = data.get("entry_id")

    if not entry_id:
        return jsonify({"error": "entry_id is required"}), 420
    
    result = ics_client.create_event(entry_id)
    if result[0]:
        return jsonify({"status": "updated", "entry_id": entry_id})
    err_code = result[1]["error_code"]
    return jsonify({"status": "error", "error_msg": result[1]["error"], "error_code": err_code}), err_code

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
