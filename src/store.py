import os
import json

class Store:
    MAPPING_FILENAME = "challenge_issues.json"
    MAPPING_PATH = os.path.join(os.path.dirname(__file__), MAPPING_FILENAME)

    @staticmethod
    def get_db():
        try:
            with open(Store.MAPPING_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def save_db(db):
        with open(Store.MAPPING_PATH, "w") as f:
            json.dump(db, f, indent=2)

    @staticmethod
    def get_key(key, default=None):
        db = Store.get_db()
        return db.get(key, default)

    @staticmethod
    def set_key(key, value):
        db = Store.get_db()
        db[key] = value
        Store.save_db(db)

    @staticmethod
    def update_key(key, update_func):
        db = Store.get_db()
        db[key] = update_func(db.get(key, {}))
        Store.save_db(db)
