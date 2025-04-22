"""
Tests for the Flask web application.
"""

import io
import os
import sys
import time
from pathlib import Path

import pytest
from bson.objectid import ObjectId

# Add the parent directory to the path to allow importing 'app'
PARENT_DIR = str(Path(__file__).parent.parent.absolute())
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app import create_app

@pytest.fixture(scope="module")
def flask_app():
    """Create and configure a Flask app for testing."""
    # Create app with test config
    test_app = create_app()
    test_app.config.update({"TESTING": True, "WTF_CSRF_ENABLED": False})

    # Wait a moment for MongoDB connection to be established
    time.sleep(1)

    # Clear all test collections before each test
    mongo_client = test_app.extensions.get("pymongo")
    if mongo_client:
        db = mongo_client[os.getenv("MONGO_DBNAME", "dot-ics")]

    return test_app


@pytest.fixture
def app(flask_app): 
    """Provide the app fixture."""
    return flask_app


@pytest.fixture
def client(app): 
    """Create a test client for the app."""
    return app.test_client()


def test_home_page_to_login(client):  
    """Test that the home page redirects to login"""
    response = client.get("/")
    assert response.status_code == 302


def test_error_handler(client): 
    """Test the error handler."""
    # Cause a deliberate exception by accessing a route that doesn't exist
    response = client.get("/bad_route")

    # Should render the error template
    assert b"error" in response.data.lower()
