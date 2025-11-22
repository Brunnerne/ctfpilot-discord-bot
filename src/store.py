import os
import json
import threading

class Store:
    MAPPING_FILENAME = "challenge_issues.json"
    MAPPING_PATH = os.path.join(os.path.dirname(__file__), MAPPING_FILENAME)
    _lock = threading.Lock()

    @staticmethod
    def _get_db_unlocked():
        """Internal method to read DB without acquiring lock (lock must be held by caller)"""
        try:
            with open(Store.MAPPING_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _save_db_unlocked(db):
        """Internal method to save DB without acquiring lock (lock must be held by caller)"""
        with open(Store.MAPPING_PATH, "w") as f:
            json.dump(db, f, indent=2)

    @staticmethod
    def get_db():
        with Store._lock:
            return Store._get_db_unlocked()

    @staticmethod
    def save_db(db):
        with Store._lock:
            Store._save_db_unlocked(db)

    @staticmethod
    def get_key(key, default=None):
        with Store._lock:
            db = Store._get_db_unlocked()
            return db.get(key, default)

    @staticmethod
    def set_key(key, value):
        with Store._lock:
            db = Store._get_db_unlocked()
            db[key] = value
            Store._save_db_unlocked(db)

    @staticmethod
    def update_key(key, update_func):
        with Store._lock:
            db = Store._get_db_unlocked()
            db[key] = update_func(db.get(key, {}))
            Store._save_db_unlocked(db)
