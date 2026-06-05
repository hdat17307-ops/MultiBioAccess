import os
import json
import pickle
import face_recognition
from config import EMPLOYEE_DB_PATH, FACE_ENCODINGS_PATH

def build_encodings() -> None:
    with open(EMPLOYEE_DB_PATH) as f:
        db = json.load(f)

    results: list[dict] = []
    for emp in db["employees"]:
        img_path = emp["face_image"]
        if not os.path.exists(img_path):
            print(f"SKIP (not found): {img_path}")
            continue
        img = face_recognition.load_image_file(img_path)
        locations = face_recognition.face_locations(img, number_of_times_to_upsample=2)
        encodings = face_recognition.face_encodings(img, locations)
        if not encodings:
            print(f"SKIP (no face detected): {img_path}")
            continue
        results.append({"encoding": encodings[0], "employee": emp})
        print(f"OK: {emp['name']}")

    os.makedirs(os.path.dirname(FACE_ENCODINGS_PATH), exist_ok=True)
    with open(FACE_ENCODINGS_PATH, "wb") as f:
        pickle.dump(results, f)
    print(f"Saved {len(results)} encodings to {FACE_ENCODINGS_PATH}")

if __name__ == "__main__":
    build_encodings()
