import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'xaika_ru_secret_key_2026_change_this_in_production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 250 * 1024 * 1024  # 250MB
    BASE_URL = 'https://xaika.ru'
