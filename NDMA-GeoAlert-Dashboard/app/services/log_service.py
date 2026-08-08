from collections import deque


def get_recent_logs(lines=200):
    try:
        with open("logs/application.log", encoding="utf-8") as file:
            return list(deque(file, maxlen=lines))
    except FileNotFoundError:
        return ["No logs available."]
