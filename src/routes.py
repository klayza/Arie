import time
from flask import Blueprint, request, jsonify, render_template_string
import openai
import os
import json
import traceback
from dotenv import load_dotenv
from datetime import datetime
import logger
from ai import AI
from codecheck import clean_code

load_dotenv()
routes = Blueprint("routes", __name__)


@routes.route("/generate_code", methods=["POST", "GET"])
def generate_code(input=None):
    if input is not None:
        user_input = input
    elif request.method == "GET":
        user_input = request.args.get("input")
    else:
        user_input = request.json.get("input") if request.is_json else None

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    # Bypass creating a new response if in cheap mode
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        return (
            jsonify(
                {
                    "code": "from pyrevit import revit, DB, forms\nforms.alert('hello world!')"
                }
            ),
            200,
        )
        # return clean_code(logger.get_logs("ai")[0]["data"].get("code", ""))

    timestamp = datetime.utcnow().isoformat()
    ai_instance = AI()

    try:
        # generated_code = 'from revit import ur_mom\nprint("deez nuts")'
        generated_code = ai_instance.generate_code(user_input)

        # When there may be an error
        if type(generated_code) == Exception:
            return jsonify({"error": str(generated_code)}), 500

        # Attempt to clean the code
        checked_code = clean_code(generated_code)

        logger.log_event(
            "ai",
            {
                "query": user_input,
                "code": checked_code,
                "model": ai_instance.model,
            },
        )

        # Finally return the code
        return jsonify({"code": checked_code}), 200

    except Exception as e:
        full_error = traceback.format_exc()
        error_message = str(e)
        logger.log_event(
            "error",
            {
                "query": user_input,
                "error": full_error,
                "model": ai_instance.model,
            },
        )
        return jsonify({"error": full_error}), 500


@routes.route("/", methods=["GET"])
def home():
    # Load all ai events
    ai_logs = logger.get_logs("ai")[::-1]

    # Load the working data as a list then convert to a dict keyed by timestamp
    working_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "working.json"
    )
    if os.path.exists(working_path):
        try:
            with open(working_path, "r") as f:
                working_list = json.load(f)
            # Create dict mapping timestamp to working value
            working_data = {
                entry["timestamp"]: entry["working"] for entry in working_list
            }
        except json.JSONDecodeError:
            working_data = {}
    else:
        working_data = {}

    # Render a simple HTML page with code blocks and checkboxes
    html = """
    <html>
      <head>
        <title>AI Events</title>
        <style>
            body {
                font-family: Cambria;
                max-width: 50%;
                margin: auto;
            }
          pre {
            background-color: #f4f4f4;
            padding: 10px;
          }
        </style>
      </head>
      <body>
        <h1>AI Events</h1>
        {% for event in ai_logs %}
          <div>
            <h3>Query: {{ event.data.query }}</h3>
            <h3>Model: {{ event.data.model }}</h3>
            <h3>Event at {{ event.timestamp }}</h3>
            <pre><code>{{ event.data.code }}</code></pre>
            <label>
              <input type="checkbox" class="working-checkbox" 
                     data-timestamp="{{ event.timestamp }}" 
                     data-query="{{ event.data.query }}"
                     {% if working_data.get(event.timestamp) %} checked {% endif %}>
              Working
            </label>
          </div>
          <hr>
        {% endfor %}
        <script>
          document.querySelectorAll('.working-checkbox').forEach(function(checkbox) {
            checkbox.addEventListener('change', function() {
              const timestamp = this.getAttribute('data-timestamp');
              const query = this.getAttribute('data-query');
              const working = this.checked;
              fetch('/update_working', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({timestamp: timestamp, query: query, working: working})
              })
              .then(response => response.json())
              .then(data => console.log(data));
            });
          });
        </script>
      </body>
    </html>
    """
    return render_template_string(html, ai_logs=ai_logs, working_data=working_data)


@routes.route("/update_working", methods=["POST"])
def update_working():
    data = request.get_json()
    timestamp = data.get("timestamp")
    query = data.get("query")
    working = data.get("working")
    working_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "working.json"
    )

    if os.path.exists(working_path):
        with open(working_path, "r") as f:
            try:
                working_data = json.load(f)
                if not isinstance(working_data, list):
                    working_data = []
            except json.JSONDecodeError:
                working_data = []
    else:
        working_data = []

    # Check if a record with the same timestamp already exists. Update if found.
    updated = False
    for record in working_data:
        if record.get("timestamp") == timestamp:
            record["working"] = working
            record["query"] = query
            updated = True
            break

    if not updated:
        working_data.append(
            {"working": working, "timestamp": timestamp, "query": query}
        )

    os.makedirs(os.path.dirname(working_path), exist_ok=True)
    with open(working_path, "w") as f:
        json.dump(working_data, f, indent=4)

    return jsonify(working_data), 200


if __name__ == "__main__":
    pass
