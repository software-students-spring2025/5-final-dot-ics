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
def app(self):
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
    db.users.drop()
    db.events.drop()
    yield db

def test_create_user(self):
    """
    test_create_user tests creating a new user and logging in.
    """
    response = self.client.post('/create_user', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)
    
    self.assertRedirects(response, '/')
    
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    user = db.users.find_one({"username": "testuser"})
    self.assertIsNotNone(user)
    self.assertEqual(user["username"], "testuser")

def test_login(self):
    """
    test_login tests logging in with the created user.
    """
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    db.users.insert_one({"username": "testuser", "password": "password"})

    response = self.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    self.assertRedirects(response, '/')
    
    with self.client:
        response = self.client.get('/')
        self.assertIn(b"testuser", response.data)

def test_logout(self):
    """
    test_logout tests logging out the user.
    """
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    db.users.insert_one({"username": "testuser", "password": "password"})

    self.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = self.client.get('/logout', follow_redirects=True)
    

    self.assertRedirects(response, '/')
    

    with self.client:
        response = self.client.get('/')
        self.assertNotIn(b"testuser", response.data)

def test_index_page(self):
    """
    test_index_page tests the index page when a user is logged in.
    """
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    user = db.users.insert_one({"username": "testuser", "password": "password"})
    db.events.insert_one({
        "user_id": user.inserted_id,
        "name": "Test Event",
        "start_time": "2025-04-21 10:00:00",
        "end_time": "2025-04-21 12:00:00",
        "location": "Test Location",
        "description": "Test Description"
    })

    self.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = self.client.get('/')
    self.assertIn(b"Test Event", response.data)
    self.assertIn(b"Test Location", response.data)

def test_invalid_date_format(self):
    """
    test_invalid_date_format tests invalid date input when creating an event or other functionality.
    """
    cxn = pymongo.MongoClient(TEST_MONGO_URI)
    db = cxn[TEST_MONGO_DBNAME]
    db.users.insert_one({"username": "testuser", "password": "password"})

    self.client.post('/login', data=dict(
        username='testuser',
        password='password'
    ), follow_redirects=True)

    response = self.client.post('/create_event', data=dict(
        name="Test Event",
        start_date="2025-99-99",  # Invalid date
        start_time="25:00",
        end_time="26:00"
    ), follow_redirects=True)

    self.assertIn(b"Invalid date", response.data)

def test_error_handling(self):
    """
    test_error_handling tests error handling route for the application.
    """
    response = self.client.get('/nonexistent_route')
    self.assertEqual(response.status_code, 404)