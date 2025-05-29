from flask import Flask
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Load configuration from environment variables if needed
    app.config['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
    
    with app.app_context():
        from . import routes

    return app