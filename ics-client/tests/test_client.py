"""
Module is responsible for the client testing class.
"""

import os
import json
import unittest
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from flask import Flask
from pymongo import MongoClient
from bson import ObjectId

from client import ICSClient
from client import app

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:secret@mongodb:27017")
TEST_DB_NAME = "test_ics_client_db"


class TestICSClient(unittest.TestCase):
    """
    Class responsible for tests.
    """

    @classmethod
    def setUpClass(cls):
        cls.mongo_client = MongoClient(MONGO_URI)
        cls.db = cls.mongo_client[TEST_DB_NAME]
        cls.collection = cls.db["events"]

    def setUp(self):
        self.collection.delete_many({})
        self.client = ICSClient()

    def test_create_dt_object_full_date_time(self):
        """
        Tests create_dt_object correctly creates a datetime
        object when both date and time are provided.
        """
        dt = self.client.create_dt_object("2025-04-22", "14:30")
        self.assertIsInstance(dt, datetime)
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 4)
        self.assertEqual(dt.day, 22)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo, ZoneInfo("America/New_York"))

    def test_create_dt_object_with_only_time(self):
        """
        Tests create_dt_object defaults to today's date 
        when only time is provided.
        """
        now = datetime.now(ZoneInfo("America/New_York"))
        dt = self.client.create_dt_object(None, "14:30")
        self.assertIsInstance(dt, datetime)
        self.assertEqual(dt.year, now.year)
        self.assertEqual(dt.month, now.month)
        self.assertEqual(dt.day, now.day)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo, ZoneInfo("America/New_York"))

    def test_create_dt_object_with_only_date(self):
        """
        Tests that create_dt_object returns a date 
        object when only the date is provided.
        """
        dt = self.client.create_dt_object("2025-04-22", None)
        self.assertIsInstance(dt, date)
        self.assertNotIsInstance(dt, datetime)
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 4)
        self.assertEqual(dt.day, 22)
    
    @patch("client.genai_client.models.generate_content")
    def test_parse_text_to_event_data_success(self, mock_generate_content):
        """
        Tests successful parsing of text into dict format.
        """
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "name": "Team Meeting",
            "date": "2025-04-25",
            "start_time": "15:00",
            "end_time": "16:00",
            "location": "Zoom",
            "description": "Weekly catch-up"
        }
        '''
        mock_generate_content.return_value = mock_response

        result = self.client.parse_text_to_event_data("Team meeting next Friday at 3-4PM on Zoom for weekly catch-up")
        print("result: ", result)
        self.assertEqual(result["name"], "Team Meeting")
        self.assertEqual(result["location"], "Zoom")
        self.assertEqual(result["description"], "Weekly catch-up")
        self.assertIsInstance(result["start"], datetime)
        self.assertIsInstance(result["end"], datetime)

    @patch("client.genai_client.models.generate_content")
    def test_parse_text_to_event_data_no_match(self, mock_generate_content):
        """
        Tests handling of invalid response text returned by llm
        """
        mock_response2 = MagicMock()
        mock_response2.text = 'bad response'
        mock_generate_content.return_value = mock_response2

        result = self.client.parse_text_to_event_data("Piano lesson next Tuesday at 3-4PM at home")
        self.assertEqual(result["error"], "No valid event extracted")

    @patch("client.genai_client.models.generate_content")
    def test_parse_text_to_event_data_invalid_time(self, mock_generate_content):
        """
        Tests handling of invalid event times in parsed data.
        """
        mock_response = MagicMock()
        mock_response.text = '''
        {
            "name": "Team Meeting",
            "date": "2025-04-25",
            "start_time": "15:00",
            "end_time": "14:00",  
            "location": "Zoom",
            "description": "Weekly catch-up"
        }
        '''
        mock_generate_content.return_value = mock_response

        result = self.client.parse_text_to_event_data("Team meeting next Friday at 4-3PM on Zoom")
        self.assertEqual(result["error"], "End time cannot be before start time.")
        self.assertEqual(result["error_code"], 402)

    def test_format_event_data_datetime_fields(self):
        """
        Tests that datetime fields in event data are formatted correctly into strings.
        """
        data = {
            "name": "Dinner with Friends",
            "start": datetime(2025, 4, 23, 18, 0, 0),
            "end": datetime(2025, 4, 23, 20, 0, 0),
        }
        formatted = self.client.format_event_data(data)
        self.assertEqual(formatted["name"],"Dinner with Friends")
        self.assertEqual(formatted["start"], "Apr 23, 2025  6:00PM")
        self.assertEqual(formatted["end"], "Apr 23, 2025  8:00PM")
        
    def test_format_event_data_date_only(self):
        """
        Tests that a date event is formatted correctly into a string.
        """
        data = {
            "name": "Christmas",
            "date": date(2025, 12, 25),
        }
        formatted = self.client.format_event_data(data)
        self.assertEqual(formatted["date"], "Dec 25, 2025")

    def test_format_event_data_with_missing_name(self):
        """
        Tests that the event name defaults to 'New Event' when missing.
        """
        data = {
            "start": datetime(2025, 4, 22, 10, 0),
        }
        formatted = self.client.format_event_data(data)
        self.assertEqual(formatted["name"], "New Event")

    def test_format_event_data_with_string_values(self):
        """
        Tests that string fields (name, location, and description)
        are preserved during formatting.
        """
        data = {
            "name": "Dinner",
            "location": "The Bistro",
            "description": "Friends night out"
        }
        formatted = self.client.format_event_data(data)
        self.assertEqual(formatted["name"], "Dinner")
        self.assertEqual(formatted["location"], "The Bistro")
        self.assertEqual(formatted["description"], "Friends night out")

    @patch("client.events_collection")
    @patch.object(ICSClient, "format_event_data")
    @patch("builtins.open", new_callable=mock_open, read_data=b"BEGIN:VCALENDAR\nEND:VCALENDAR")
    def test_store_event(self, mock_open_file, mock_format_event_data, mock_events_collection):
        """
        Tests the store_event method to ensure it writes 
        formatted data and ICS file content to MongoDB.
        """
        entry_id = "67f6d1236aaf92738f8f8855"
        ics_path = "./events/dummy.ics"
        object_id = ObjectId(entry_id)

        event_data = {
            'name': 'Group project meeting', 
            'start': datetime(2025, 4, 23, 15, 0, tzinfo=ZoneInfo(key='America/New_York')), 
            'end': datetime(2025, 4, 23, 16, 0, tzinfo=ZoneInfo(key='America/New_York')), 
            'location': 'Silver Building',
            'description': None,
        }
        mock_formatted_data = {
            'name': 'Group project meeting', 
            'start': 'Apr 23, 2025  3PM', 
            'end': 'Apr 23, 2025  4PM', 
            'location': 'Silver Building',
            'description': None,
        }
        mock_format_event_data.return_value = mock_formatted_data

        self.client.store_event(entry_id, event_data, ics_path)

        mock_open_file.assert_called_once_with(ics_path, "rb")
        mock_open_file().read.assert_called_once()
        mock_format_event_data.assert_called_once_with(event_data)
        mock_events_collection.update_one.assert_called_once_with(
            {"_id": object_id},
            {
                "$set": {
                    "event_data": mock_formatted_data,
                    "ics_file": b"BEGIN:VCALENDAR\nEND:VCALENDAR",
                    "ics_file_path": ics_path,
                }
            }
        )

    @patch("client.events_collection.find_one")
    @patch.object(ICSClient, "parse_text_to_event_data")
    @patch("client.ICSClient.store_event")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_create_event_success(self, mock_mkdir, mock_open_file,
                                  mock_store_event, mock_parse_text, mock_find_one):
        """
        Tests successful flow of create_event: 
        read from DB, parse text, creating .ics, and saving to DB.
        """
        entry_id = "67f6d1236aaf92738f8f8855"
        object_id = ObjectId(entry_id)

        mock_find_one.return_value = {
            "text": "Meeting at 3PM in Room 101 to discuss club activities"
        }

        mock_event_data = {
            "name": "Meeting",
            "start": datetime(2025, 4, 23, 15, 0, tzinfo=ZoneInfo("America/New_York")),
            "end": datetime(2025, 4, 23, 16, 0, tzinfo=ZoneInfo("America/New_York")),
            "description": "Discuss club activities",
            "location": "Room 101"
        }
        mock_parse_text.return_value = mock_event_data

        result = self.client.create_event(entry_id)

        self.assertTrue(result[0])
        mock_find_one.assert_called_once_with({"_id": object_id}, {"text": 1})
        mock_parse_text.assert_called_once_with("Meeting at 3PM in Room 101 to discuss club activities")
        mock_open_file.assert_called_once_with(Path(f"./events/{entry_id}.ics"), "wb")
        mock_open_file().write.assert_called_once()
        mock_mkdir.assert_called_once()
        mock_store_event.assert_called_once()

    @patch("client.events_collection.find_one")
    def test_create_event_no_text(self, mock_find_one):
        """
        Tests create_event behavior when the database entry has no text value.
        """
        entry_id = "67f6d1236aaf92738f8f8855"
        object_id = ObjectId(entry_id) 
        mock_find_one.return_value = {"text": None}

        result = self.client.create_event(entry_id)

        self.assertFalse(result[0])
        mock_find_one.assert_called_once_with({"_id": object_id}, {"text": 1})

    @patch.object(ICSClient, "parse_text_to_event_data")
    @patch("client.events_collection.find_one")
    def test_create_event_with_error(self, mock_find_one, mock_parse_text):
        """Test that create_event raises ValueError when parsing fails."""
        entry_id = "67f6d1236aaf92738f8f8855"
        mock_find_one.return_value = {"text": "bad input"}
        mock_parse_text.return_value = {"error": "Invalid event format", "error_code": 403}

        result = self.client.create_event(entry_id)

        self.assertFalse(result[0])
        self.assertEqual(result[1], {"error": "Invalid event format", "error_code": 403})


class TestProcessRequestRoute(unittest.TestCase):
    """
    Test suite for the /run-client route.
    """

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_missing_entry_id(self):
        """
        Tests /run-client route returns 420 if no entry_id is provided.
        """
        response = self.client.post("/run-client", json={})
        self.assertEqual(response.status_code, 420)
        self.assertEqual(response.get_json(), {"error": "entry_id is required"})

    @patch("client.ics_client.create_event")
    def test_create_event_success(self, mock_create_event):
        """
        Tests handling of /run-client route when 
        event is create_event executes successfully
        """
        mock_create_event.return_value = (True, None)
        response = self.client.post("/run-client", json={"entry_id": "abc123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "updated", "entry_id": "abc123"})
        mock_create_event.assert_called_once_with("abc123")

    @patch("client.ics_client.create_event")
    def test_create_event_failure(self, mock_create_event):
        """
        Tests /run-client route returns an error when ICS event creation fails.
        """
        mock_create_event.return_value = (False, {"error": "No text found in the entry.", "error_code": 421})
        response = self.client.post("/run-client", json={"entry_id": "abc123"})
        self.assertEqual(response.status_code, 421)
        self.assertEqual(response.get_json(), 
                         {"status": "error", "error_msg": "No text found in the entry.", "error_code": 421})
        mock_create_event.assert_called_once_with("abc123")

if __name__ == "__main__":
    unittest.main()
