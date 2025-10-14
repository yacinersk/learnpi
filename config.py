import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///db.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret')
    BUNNY_API_KEY = os.getenv('BUNNY_API_KEY')
    BUNNY_STORAGE_ZONE = os.getenv('BUNNY_STORAGE_ZONE')
    PI_API_KEY = os.getenv('PI_API_KEY')
    PI_CALLBACK_SECRET = os.getenv('PI_CALLBACK_SECRET')
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
