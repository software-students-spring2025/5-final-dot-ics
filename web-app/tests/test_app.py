import pytest
from flask import Flask
from flask_testing import TestCase
from flask_login import current_user
from bson import ObjectId
import pymongo
import os

from app import create_app

TEST_MONGO_URI = "mongodb://admin:secret@mongodb:27017/"
TEST_MONGO_DBNAME = "test_db"

@pytest.fixture(scope="session")
def app(request):
    app = create_app()
    app.config["MONGO_URI"] = TEST_MONGO_URI
    app.config["MONGO_DBNAME"] = TEST_MONGO_DBNAME
    app.config["TESTING"] = True
    app.config["FLASK_ENV"] = "development"
    app.secret_key = 'secret'
    yield app

@pytest.fixture
def client(app):  # pylint: disable=redefined-outer-name
    """Create a test client for the app."""
    return app.test_client()

@pytest.fixture(scope="session", autouse=True)
def mongo(app):
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    yield db
    db.users.drop()
    db.events.drop() 

def test_create_user(client, mongo):
    """
    test_create_user tests creating a new user and logging in.
    """
    response = client.post('/create_user', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)
    
    assert response.status_code == 302
    
    user = mongo.users.find_one({"username": "testuser"})

    assert user is not None
    assert user["username"] ==  "testuser"

def test_login(client, mongo):
    """
    test_login tests logging in with the created user.
    """

    mongo.users.insert_one({"username": "testuser", "password": "password"})

    response = client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    assert response.status_code == 302
    
    with client:
        response = client.get('/')
        assert b"testuser" in response.data

def test_logout(client, mongo):
    """
    test_logout tests logging out the user.
    """

    mongo.users.insert_one({"username": "testuser", "password": "password"})

    client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = client.get('/logout', follow_redirects=True)
    

    client.assertRedirects(response, '/')

    with client:
        response = client.get('/')
        assert b"testuser" not in response.data

def test_index_page(client, mongo):
    """
    test_index_page tests the index page when a user is logged in.
    """

    user = mongo.users.insert_one({"username": "testuser", "password": "password"})
    mongo.events.insert_one({
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

def test_invalid_date_format(client, mongo):
    """
    test_invalid_date_format tests invalid date input when creating an event or other functionality.
    """

    mongo.users.insert_one({"username": "testuser", "password": "password"})

    client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = client.post('/create_event', data=dict(
        name="Test Event",
        start_date="2025-99-99",  # Invalid date
        start_time="25:00",
        end_time="26:00"
    ), follow_redirects=True)

    assert b"Invalid date" in response.data

def test_error_handling(client):
    """
    test_error_handling tests error handling route for the application.
    """
    response = client.get('/nonexistent_route')
    assert  b"error" in response.data