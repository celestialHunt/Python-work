import os
from dotenv import load_dotenv  # cspell:ignore dotenv
from flask import Flask
from flask_smorest import Api
from app.api import register_blueprints
from app.database import db
from urllib.parse import quote_plus

load_dotenv()


def create_app():
    app = Flask(__name__)

    # Get values from .env
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    dbname = os.getenv("DB_NAME")

    if password is None:
        raise ValueError(
            "Could not find DB_PASSWORD in .env file. Check the file path!"
            )
    safe_password = quote_plus(password)

    # Set the Database URL
    DATABASE_URL = (
        f"mysql+mysqldb://{user}:{safe_password}@{host}:{port}/{dbname}"
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Flask-Smorest config
    app.config["API_TITLE"] = "My First API"
    app.config["API_VERSION"] = "1.0"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger"
    app.config["OPENAPI_SWAGGER_UI_URL"] = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    )
    db.init_app(app)
    api = Api(app)

    register_blueprints(api)

    return app
