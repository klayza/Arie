import json
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOG_FILE = os.path.join(LOG_DIR, "events.json")


def log_event(log_type, data):
    """
    Logs an event of the specified type with the given data.
    Args:
        log_type (str): The type of event (e.g., "ai", "error", etc.).
        data (dict): A dictionary of data to log.
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "log_type": log_type,
        "data": data,
    }
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


def get_logs(log_type=None):
    """
    Retrieves logged events, optionally filtered by type.
    Args:
        log_type (str, optional): If provided, only returns logs of this type.
    Returns:
        list: List of log entries.
    """
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
            if log_type:
                return [log for log in logs if log["log_type"] == log_type]
            return logs
    except json.JSONDecodeError:
        return []
