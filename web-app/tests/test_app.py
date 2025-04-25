import pytest
from flask import Flask
from bson import ObjectId
import pymongo
import os

from app import create_app

TEST_MONGO_URI = "mongodb://admin:secret@mongodb:27017/"
TEST_MONGO_DBNAME = "test_db"

@pytest.fixture(scope="session")
def flask_app():
    app = create_app()
    app.config.update({"TESTING": True, "WTF_CSRF_ENABLED": False})
    return app

@pytest.fixture
def app(flask_app): 
    """Provide the app fixture."""
    return flask_app

@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()

@pytest.fixture(scope="session")
def mongodb():
    """Create a test mongodb client"""
    client = pymongo.MongoClient(os.environ["MONGO_URI"])
    assert client.admin.command("ping")["ok"] != 0.0  # Check that the connection is okay.
    return client

def test_create_user(client, mongodb):
    """
    test_create_user tests creating a new user and logging in.
    """
    response = client.post('/create_user', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)
    
    assert response.status_code == 200
    
    user = mongodb["dot-ics"].users.find_one({"username": "testuser"})

    assert user is not None
    assert user["username"] ==  "testuser"

def test_login(client, mongodb):
    """
    test_login tests logging in with the created user.
    """

    mongodb["dot-ics"].users.insert_one({"username": "testuser", "password": "password"})

    response = client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)
    
    with client:
        response = client.get('/')
        assert b"ICS File Generator" in response.data

def test_logout(client, mongodb):
    """
    test_logout tests logging out the user.
    """

    mongodb["dot-ics"].users.insert_one({"username": "testuser", "password": "password"})

    client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = client.get('/logout', follow_redirects=True)
    
    with client:
        response = client.get('/')
        assert response.status_code == 302

def test_index_page(client, mongodb):
    """
    test_index_page tests the index page when a user is logged in.
    """

    user =  mongodb["dot-ics"].users.insert_one({"username": "testuser", "password": "password"})

    mongodb["dot-ics"].events.insert_one({
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
    print(response.data)
    assert b"Test Event" in response.data

def test_generate_event(client,mongodb):
    """
    test_generate_event tests the route to take a prompt and generate an event in the database
    """

    user =  mongodb["dot-ics"].users.insert_one({"username": "testuser", "password": "password"})

    client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    client.post('/generate_event', data={
        "event-description-input": "Group project meeting tmr at 10 at night in  Silver Building conference room."
    }, follow_redirects=True)

    event = mongodb["dot-ics"].events.find_one({'user_id': user.inserted_id})

    assert event is not None

    response = client.get('/')
    assert b"group project" in response.data.lower()

def test_download(client,mongodb):
    user =  mongodb["dot-ics"].users.insert_one({"username": "testuser", "password": "password"})

    event = mongodb["dot-ics"].events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event 2",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    response = client.post(f"/download/{str(event.inserted_id)}", data={
        "id":event.inserted_id
    }, follow_redirects = True)

    assert response.status_code == 200
    assert response.mimetype =='text/calendar'


def test_delete(client, mongodb):
    user =  mongodb["dot-ics"].users.insert_one({"username": "testuser", "password": "password"})

    event = mongodb["dot-ics"].events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event 2",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    client.post(f"/delete/{str(event.inserted_id)}", data={
        "id":event.inserted_id
    }, follow_redirects = True)

    check = mongodb["dot-ics"].events.find_one({"_id": event.inserted_id})

    assert check is None


def test_error_handling(client):
    """
    test_error_handling tests error handling route for the application.
    """
    response = client.get('/nonexistent_route')
    assert  b"error" in response.data