import json
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "ai.json")


def log_ai_query(query, code, timestamp, model):
    log_entry = {"timestamp": timestamp, "query": query, "code": code, "model": model}

    os.makedirs(LOG_DIR, exist_ok=True)

    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        except json.JSONDecodeError:
            logs = []
    logs.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)
