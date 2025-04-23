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

@pytest.fixture(scope="session", autouse=True)
def mongo(app):
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    yield db
    db.users.drop()
    db.events.drop() 

def test_create_user(app, mongo):
    """
    test_create_user tests creating a new user and logging in.
    """
    response = app.client.post('/create_user', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)
    
    app.assertRedirects(response, '/')
    
    user = mongo.db.users.find_one({"username": "testuser"})
    app.assertIsNotNone(user)
    app.assertEqual(user["username"], "testuser")

def test_login(app, mongo):
    """
    test_login tests logging in with the created user.
    """

    mongo.db.users.insert_one({"username": "testuser", "password": "password"})

    response = app.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    app.assertRedirects(response, '/')
    
    with app.client:
        response = app.client.get('/')
        app.assertIn(b"testuser", response.data)

def test_logout(mongo):
    """
    test_logout tests logging out the user.
    """

    mongo.db.users.insert_one({"username": "testuser", "password": "password"})

    app.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = app.client.get('/logout', follow_redirects=True)
    

    app.assertRedirects(response, '/')
    

    with app.client:
        response = app.client.get('/')
        app.assertNotIn(b"testuser", response.data)

def test_index_page(mongo):
    """
    test_index_page tests the index page when a user is logged in.
    """

    user = mongo.db.users.insert_one({"username": "testuser", "password": "password"})
    mongo.db.events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    app.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = app.client.get('/')
    app.assertIn(b"Test Event", response.data)
    app.assertIn(b"Test Location", response.data)

def test_invalid_date_format(mongo):
    """
    test_invalid_date_format tests invalid date input when creating an event or other functionality.
    """

    mongo.db.users.insert_one({"username": "testuser", "password": "password"})

    app.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = app.client.post('/create_event', data=dict(
        name="Test Event",
        start_date="2025-99-99",  # Invalid date
        start_time="25:00",
        end_time="26:00"
    ), follow_redirects=True)

    app.assertIn(b"Invalid date", response.data)

def test_error_handling(app):
    """
    test_error_handling tests error handling route for the application.
    """
    response = app.client.get('/nonexistent_route')
    app.assertEqual(response.status_code, 404)