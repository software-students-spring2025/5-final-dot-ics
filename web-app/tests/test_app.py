import pytest
from flask import Flask
from flask_testing import TestCase
from flask_login import current_user
from bson import ObjectId
import pymongo
import os
import time

from app import create_app

TEST_MONGO_URI = "mongodb://admin:secret@mongodb:27017/"
TEST_MONGO_DBNAME = "test_db"

@pytest.fixture(scope="module")
def flask_app():
    app = create_app()
    app.config.update({"TESTING": True, "WTF_CSRF_ENABLED": False})

    # Wait a moment for MongoDB connection to be established
    time.sleep(1)

    mongo_client = app.extensions.get("pymongo")
    if mongo_client:
        db = mongo_client[TEST_MONGO_DBNAME]

    return app

@pytest.fixture
def app(flask_app): 
    """Provide the app fixture."""
    return flask_app

@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


def test_create_user(client, app):
    """
    test_create_user tests creating a new user and logging in.
    """
    response = client.post('/create_user', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    assert b"testuser" in response.data

    db = app.extensions.get("mongodb")
    if db is None:
        pytest.skip("MongoDB connection not available")
    
    user = db.users.find_one({"username": "testuser"})

    assert user is not None
    assert user["username"] ==  "testuser"

def test_login(client, app):
    """
    test_login tests logging in with the created user.
    """

    db = app.extensions.get("mongodb")
    if db is None:
        pytest.skip("MongoDB connection not available")

    db.users.insert_one({"username": "testuser", "password": "password"})

    response = client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)
    
    with client:
        response = client.get('/')
        assert b"testuser" in response.data

def test_logout(client, app):
    """
    test_logout tests logging out the user.
    """

    db = app.extensions.get("mongodb")
    if db is None:
        pytest.skip("MongoDB connection not available")

    db.users.insert_one({"username": "testuser", "password": "password"})

    client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = client.get('/logout', follow_redirects=True)
    
    client.assertRedirects(response, '/')

    with client:
        response = client.get('/')
        assert b"testuser" not in response.data

def test_index_page(client, app):
    """
    test_index_page tests the index page when a user is logged in.
    """

    db = app.extensions.get("mongodb")
    if db is None:
        pytest.skip("MongoDB connection not available")

    user = db.users.insert_one({"username": "testuser", "password": "password"})
    db.events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = client.get('/')
    assert b"Test Event" in response.data
    assert b"Test Location" in response.data

def test_error_handling(client):
    """
    test_error_handling tests error handling route for the application.
    """
    response = client.get('/nonexistent_route')
    assert  b"error" in response.data