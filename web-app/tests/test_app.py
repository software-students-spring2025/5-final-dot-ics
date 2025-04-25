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
    os.environ["MONGO_URI"] = TEST_MONGO_URI
    os.environ["MONGO_DBNAME"] = TEST_MONGO_DBNAME
    os.environ["SECRET_KEY"] = "test-secret-key"

    app = create_app()
    app.config.update({"TESTING": True, "WTF_CSRF_ENABLED": False})
    return app

@pytest.fixture
def app(flask_app): 
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(scope="function", autouse=True)
def clean_db():
    """Ensure database is clean between tests."""
    client = pymongo.MongoClient(TEST_MONGO_URI)
    db = client[TEST_MONGO_DBNAME]
    db.users.delete_many({})
    db.events.delete_many({})
    yield
    db.users.delete_many({})
    db.events.delete_many({})

@pytest.fixture(scope="session")
def mongodb():
    client = pymongo.MongoClient(TEST_MONGO_URI)
    assert client.admin.command("ping")["ok"] != 0.0
    return client

def test_create_user(client, mongodb):
    response = client.post('/create_user', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    assert response.status_code == 200
    user = mongodb[TEST_MONGO_DBNAME].users.find_one({"username": "testuser"})
    assert user is not None

def test_login(client, mongodb):
    mongodb[TEST_MONGO_DBNAME].users.insert_one({"username": "testuser", "password": "password"})
    client.post('/login', data=dict(
        username='testuser', password='password'
        ), follow_redirects=True)

    response = client.get('/')
    assert b"ICS File Generator" in response.data or response.status_code == 200

def test_logout(client, mongodb):
    mongodb[TEST_MONGO_DBNAME].users.insert_one({"username": "testuser", "password": "password"})
    client.post('/login', data=dict(
        username='testuser', password='password'
        ), follow_redirects=True)

    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200

def test_index_page(client, mongodb):
    user = mongodb[TEST_MONGO_DBNAME].users.insert_one({"username": "testuser", "password": "password"})
    mongodb[TEST_MONGO_DBNAME].events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    client.post('/login', data=dict(
        username='testuser', password='password'
        ), follow_redirects=True)
    response = client.get('/')
    assert b"Test Event" in response.data

def test_generate_event(client, mongodb, monkeypatch):
    user = mongodb[TEST_MONGO_DBNAME].users.insert_one({"username": "testuser", "password": "password"})
    client.post('/login', data=dict(username='testuser', password='password'), follow_redirects=True)

    # Mock requests.post to mimic ML client response
    def mock_post(url, json, timeout):
        class MockResponse:
            def __init__(self):
                self.status_code = 200
            def json(self):
                return {"status": "success", "entry_id": json["entry_id"]}
        return MockResponse()

    monkeypatch.setattr("requests.post", mock_post)

    response = client.post('/generate-event', data={
        "event-description-input": "Group project meeting tomorrow at 10pm in Silver Building."
    }, follow_redirects=True)

    assert response.status_code == 200
    event = mongodb[TEST_MONGO_DBNAME].events.find_one({'user_id': user.inserted_id})
    assert event is not None

def test_download(client, mongodb):
    user = mongodb[TEST_MONGO_DBNAME].users.insert_one({"username": "testuser", "password": "password"})
    event = mongodb[TEST_MONGO_DBNAME].events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event 2",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description",
        "ics_file": "BEGIN:VCALENDAR\nEND:VCALENDAR"
    })

    response = client.get(f"/download/{str(event.inserted_id)}")
    assert response.status_code == 200
    assert response.content_type == 'text/calendar'

def test_delete(client, mongodb):
    user = mongodb[TEST_MONGO_DBNAME].users.insert_one({"username": "testuser", "password": "password"})
    event = mongodb[TEST_MONGO_DBNAME].events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event 2",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    client.get(f"/delete/{str(event.inserted_id)}", follow_redirects=True)
    check = mongodb[TEST_MONGO_DBNAME].events.find_one({"_id": event.inserted_id})
    assert check is None

def test_error_handling(client):
    response = client.get('/nonexistent_route')
    assert b"error" in response.data or response.status_code == 404
