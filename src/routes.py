from flask import Blueprint, request, jsonify
import openai
import os
from dotenv import load_dotenv
from datetime import datetime
import logger  # import the logs handler

load_dotenv()

routes = Blueprint("routes", __name__)


@routes.route("/generate_code", methods=["POST", "GET"])
def generate_code(input=None):
    user_input = input if input is not None else request.json.get("input")

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    try:
        system_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "system.txt"
        )
        with open(system_file_path, "r") as f:
            system_prompt = f.read().strip()
    except Exception as e:
        return jsonify({"error": "System prompt file not found"}), 500

    openai.api_key = os.getenv("OPENAI_API_KEY")
    model = "gpt-4.1-mini-2025-04-14"
    timestamp = datetime.utcnow().isoformat()

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
        )
        generated_code = response.choices[0].message.content
        logger.log_ai_query(
            query=user_input, code=generated_code, timestamp=timestamp, model=model
        )
        return jsonify({"generated_code": generated_code}), 200
    except Exception as e:
        error_message = str(e)
        logger.log_ai_query(
            query=user_input, code=error_message, timestamp=timestamp, model=model
        )
        return jsonify({"error": error_message}), 500


if __name__ == "__main__":
    from server import create_app

    app = create_app()
    with app.app_context():
        print(
            generate_code(
                "list all dimension lengths on the active view and find the shortest length"
            )
        )
