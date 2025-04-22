"""
Module is responsible for the client testing class.
"""

from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import json
import unittest
from unittest.mock import patch
from pymongo import MongoClient

from client import ICSClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:secret@mongodb:27017")
TEST_DB_NAME = "test_ics_client_db"

class TestICSClient(unittest.TestCase):
    """
    Class responsible for tests.
    """

    @classmethod
    def setUpClass(cls):
        oad_dotenv()
        cls.mongo_client = MongoClient(MONGO_URI)
        cls.db = cls.mongo_client[TEST_DB_NAME]
        cls.collection = cls.db["events"]

    def setUp(self):
        self.collection.delete_many({})
        self.client = ICSClient()

    def test_api_key_is_loaded(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        self.assertIsNotNone(api_key, "API key not loaded from .env file")

    @patch("client.model.generate_content")
    def test_parse_event_and_store(self, mock_generate):
        """
        test_parse_event_and_store tests the parsing of the event,
        stores it, then checks if the store was successful.
        """

        # Mock response
        mock_event_json = {
            "name": "Dinner with Friends",
            "date": "2025-04-20",
            "start_time": "18:00",
            "end_time": "20:00",
            "location": "The Diner",
            "description": "Chill evening dinner",
        }
        mock_generate.return_value.text = json.dumps(mock_event_json)

        text_input = "Dinner with Friends at The Diner at 6pm Sunday"
        event_data = self.client.parse_text_to_event_data(text_input)

        self.assertEqual(event_data["name"], "Dinner with Friends")
        self.assertEqual(event_data["location"], "The Diner")
        self.assertIsInstance(event_data["start"], datetime)
        self.assertEqual(event_data["start"].tzinfo, ZoneInfo("America/New_York"))

        # Write ICS file
        dummy_ics_path = Path("./events/event.ics")
        dummy_ics_path.parent.mkdir(exist_ok=True)
        dummy_ics_path.write_text("BEGIN:VCALENDAR...", encoding="utf-8")

        self.client.store_event(event_data, dummy_ics_path)

        # Check insert
        stored = self.collection.find_one({"name": "Dinner with Friends"})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["location"], "The Diner")
        self.assertIn("ics_file", stored)

    def test_create_dt_object(self):
        """
        test_create_dt_object tests if the datetime method works properly.
        """

        dt = self.client.create_dt_object("2025-04-22", "14:30")
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo, ZoneInfo("America/New_York"))

    @patch("client.model.generate_content")
    def test_create_event_full_flow(self, mock_generate):
        """
        test_create_event_full_flow tests if a created & stored event
        exists within the MongoDB.
        """

        mock_generate.return_value.text = json.dumps(
            {
                "name": "Team Sync",
                "date": "2025-04-21",
                "start_time": "09:00",
                "end_time": "09:30",
                "location": "Zoom",
                "description": "Weekly stand-up",
            }
        )

        ics_path = self.client.create_event("Team sync on Monday at 9am over Zoom")
        self.assertTrue(Path(ics_path).exists())

        stored = self.collection.find_one({"name": "Team Sync"})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["description"], "Weekly stand-up")
        Path(ics_path).unlink()

    def test_parse_invalid_event(self):
        """
        test_parse_invalid_event tests when input does not contain a valid event.
        """
        invalid_text = "Just some random text"
        event_data = self.client.parse_text_to_event_data(invalid_text)
        self.assertIn("error", event_data)
        self.assertEqual(event_data["error"], "No valid event extracted")

    def test_invalid_date_time(self):
        """
        test_invalid_date_time tests invalid date time formats are handled properly.
        """
        invalid_date = "2025-99-99"
        invalid_time = "25:00"
        dt = self.client.create_dt_object(invalid_date, invalid_time)
        self.assertIsNone(dt)

        dt_invalid_time = self.client.create_dt_object("2025-04-20", "25:00")
        self.assertIsNone(dt_invalid_time)

        dt_invalid_date = self.client.create_dt_object("2025-99-99", "14:30")
        self.assertIsNone(dt_invalid_date)

    def test_create_event_invalid_data(self):
        """
        test_create_event_invalid_data tests that create_event method raises exception for invalid data.
        """
        invalid_text = "Invalid event data with no date or location"
        with self.assertRaises(ValueError):
            self.client.create_event(invalid_text)

    @patch("pymongo.MongoClient")
    def test_mongo_unreachable(self, mock_mongo_client):
        """
        test_mongo_unreachable tests how ICSClient handles MongoDB being unreachable.
        """
        mock_mongo_client.side_effect = Exception("MongoDB connection failed")
        with self.assertRaises(Exception):
            client = ICSClient()

    def test_store_event_invalid_file(self):
        """
        test_store_event_invalid_file tests how store_event handles bad ICS paths.
        """
        invalid_path = Path("./non_existent_path/invalid_file.ics")
        event_data = {"name": "Test Event", "start": datetime.now(), "end": datetime.now(), "location": "Test Location"}

        with self.assertRaises(FileNotFoundError):
            self.client.store_event(event_data, invalid_path)



if __name__ == "__main__":
    unittest.main()
