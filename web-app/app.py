"""This is a Flask Web App"""

import os
import logging
from flask import (
    Flask,
    render_template,
    request,
    url_for,
    redirect,
    session
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_required,
    login_user
)
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
        user_info = db.users.find_one({"_id": user_id})
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
                app.logger.debug("* login(): user: %s", db.users.find())

                user_info = db.users.find_one({"username": username})
                if user_info:
                    if user_info["password"] == password:
                        app.logger.debug("* login(): User authenticated: %s", username)
                        current_user = User(user_info["_id"], user_info["username"])
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
                new_user = db.users.insert_one({"username": username, "password": password})
                app.logger.debug("* create_user(): Inserting User: %s", new_user.inserted_id)
                user_info = db.users.find_one({"_id": new_user.inserted_id})
                current_user = User(user_info["_id"], user_info["username"])
                app.logger.debug("* create_user(): user created: %s", current_user.username)
                login_user(current_user)
                return redirect(url_for("index"))  # Redirect if login successful
            else:
                return render_template("create_user.html", error="Please choose a different username and password")
        return render_template("create_user.html")


    @flask_app.route("/")
    @login_required
    def index():
        """
        Route for the home page.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        return render_template("index.html")

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

    return flask_app


app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)
