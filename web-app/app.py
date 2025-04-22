"""This is a Flask Web App"""

import os
import logging
import requests
from flask import (
    Flask,
    Response,
    render_template,
    request,
    url_for,
    redirect
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_required,
    login_user,
    logout_user,
    current_user
)
from datetime import datetime
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values
import pymongo



load_dotenv()  # load environment variables from .env file

def create_app():
    """
    Create and configure the Flask application.
    returns: app: the Flask application object
    """

    flask_app = Flask(__name__)
    # load flask config from env variables
    config = dotenv_values()
    flask_app.config.from_mapping(config)

    # Flask login configuration
    flask_app.secret_key = os.getenv("SECRET_KEY")
    login_manager = LoginManager()
    login_manager.init_app(flask_app)
    login_manager.login_view = "login"
    
    # Set up logging in Docker container's output
    logging.basicConfig(level=logging.DEBUG)

    # Create MongoDB connections
    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]

    try:
        cxn.admin.command("ping")
        print(" *", "Connected to MongoDB!")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(" * MongoDB connection error:", e)

    # Drop all collections to prevent duplicated data getting
    # inserted into the database whenever the app is restarted
    collections = db.list_collection_names()
    for collection in collections:
        db[collection].drop()

    class User(UserMixin):
        def __init__(self, id, username):
            self.id = str(id)
            self.username = username

        def get_id(self):
            return str(self.id)

    @login_manager.user_loader
    def load_user(user_id):
        user_info = db.users.find_one({"_id": ObjectId(user_id)})
        app.logger.debug("* load_user(): user: %s", user_info)
        if not user_info:
            return None
        current_user = User(user_info["_id"], user_info["username"])
        return current_user

    @flask_app.route("/login", methods=["GET", "POST"])
    def login():
        """
        Route for the login page.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            # Authentication logic
            if username and password:
                app.logger.debug("* login(): Authenticating user: %s", username)
                user_info = db.users.find_one({"username": username})
                app.logger.debug("* login(): user: %s", user_info)

                if user_info:
                    if user_info["password"] == password:
                        app.logger.debug("* login(): User authenticated: %s", username)
                        current_user = User(id=user_info["_id"], username=user_info["username"])
                        login_user(current_user)
                        return redirect(url_for("index"))  # Redirect if login successful
                    else:
                        return render_template("login.html", error="Incorrect Password")
                else:
                    return render_template("login.html", error="User not found. Please create an account") 

        return render_template("login.html")

    @flask_app.route("/create_user", methods=["GET", "POST"])
    def create_user():
        """
        Route for the create_user page.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            if username and password:
                if db.users.find_one({"username": username}):
                    return render_template("create_user.html", error="Please choose a different username")
                new_user = db.users.insert_one({"username": username, "password": password})
                app.logger.debug("* create_user(): Inserting User: %s", new_user.inserted_id)
                user_info = db.users.find_one({"_id": ObjectId(new_user.inserted_id)})
                current_user = User(id=user_info["_id"], username=user_info["username"])
                app.logger.debug("* create_user(): user created: %s", current_user.username)
                login = login_user(current_user)
                app.logger.debug("* create_user(): login success: %s", login)
                return redirect(url_for("index"))  # Redirect if login successful

        return render_template("create_user.html")
    
    @flask_app.route("/logout")
    @login_required
    def logout():
        """
        Route for logging user out
        """
        logout_user()
        return redirect(url_for("index"))

    @flask_app.route("/")
    @login_required
    def index():
        """
        Route for the home page.
        Returns:
            rendered template (str): The rendered HTML template.
        """

        #find user with user id then fetch the events of that user
        user_id = current_user.get_id()
        events = db.events.find({"user_id": user_id})
        event_list = list(events)
        return render_template("index.html", events = event_list)
    
    @flask_app.route("/download/<id>")
    def download_ics(id):
        """
        Stream ics file from MongoDB

        Args:
            id: The ID of the ics event

        Returns:
            rendered template (str): The rendered HTML template.
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(id)

            # Get the data from MongoDB
            event_doc = db.events.find({'_id': object_id})

            # Return the image as a response
            return Response(event_doc['ics_file'], mimetype='text/calendar')

        except Exception as e:
            flask_app.logger.error("Error streaming ics: %s", str(e))
            return handle_error(e)
    
    @flask_app.route("/delete/<id>")
    def delete(id):
        """
        Delete event from MongoDB

        Args:
            id: The ID of the ics event

        Returns:
            ICS file response
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(id)

            # Get the data from MongoDB
            event_doc = db.events.delete_one({'_id': object_id})

            # Return the image as a response
            return redirect(url_for("index"))

        except Exception as e:
            flask_app.logger.error("Error deleting event: %s", str(e))
            return handle_error(e)
    


    @flask_app.errorhandler(Exception)
    def handle_error(e):
        """
        Output any errors - good for debugging.
        Args:
            e (Exception): The exception object.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        return render_template("error.html", error=e)
    
    @flask_app.route("/generate-event", methods=["POST"])
    @login_required
    def generate_event():
        """
        Route that handles form submission to generate a 
        calendar event from user input.

        This route takes the event description submitted by the user, stores 
        it in the database, and then triggers the ICS generation process.
        """
       
        text = request.form["event-description-input"]
        user_id = current_user.get_id()
        doc = {
            "user_id": ObjectId(user_id),
            "text": text,
            "created_at": datetime.now()
        }

        new_entry_id = db.events.insert_one(doc).inserted_id
        app.logger.debug("* generate_event(): Inserted 1 entry: %s", new_entry_id)

        # Trigger the /run-client endpoint in the ml_client service
        run_client_url = "http://ics-client:5001/run-client"
        try:
            response = requests.post(
                run_client_url,
                json={"entry_id": str(new_entry_id)},
                timeout=5,
            )
        except requests.exceptions.RequestException as e:
            app.logger.error("*** generate_event(): Request failed: %s", e)
            return "Error creating ICS file", 500

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            updated_entry_id = data.get("entry_id")

            app.logger.debug(
                "*** generate_event(): status=%s, entry_id=%s",
                status,
                updated_entry_id,
            )
            return redirect(url_for("index"))
        return "Error creating ICS file", 500

    return flask_app


app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)
