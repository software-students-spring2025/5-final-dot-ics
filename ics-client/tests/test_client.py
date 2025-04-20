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
        cls.mongo_client = MongoClient(MONGO_URI)
        cls.db = cls.mongo_client[TEST_DB_NAME]
        cls.collection = cls.db["events"]

    def setUp(self):
        self.collection.delete_many({})
        self.client = ICSClient()

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


if __name__ == "__main__":
    unittest.main()
