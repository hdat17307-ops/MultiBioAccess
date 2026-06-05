import cv2
import numpy as np
import face_recognition
import pickle
import os
from config import (
    MIN_FACE_DISTANCE, MAX_FACE_DISTANCE,
    NEUTRAL_COLOR, FACE_MATCH_TOLERANCE, FACE_ENCODINGS_PATH
)

class FaceDetectorModule:
    def __init__(self) -> None:
        self.encodings_db: list[dict] = self._load_encodings()

    def _load_encodings(self) -> list[dict]:
        if os.path.exists(FACE_ENCODINGS_PATH):
            with open(FACE_ENCODINGS_PATH, "rb") as f:
                return pickle.load(f)
        return []

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, list, list]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")
        bboxes = []
        scores = []
        for (top, right, bottom, left) in locations:
            x, y, w, h = left, top, right - left, bottom - top
            bbox = {"bbox": [x, y, w, h]}
            bboxes.append(bbox)
            scores.append(1.0)
            cv2.rectangle(frame, (x, y), (x + w, y + h), NEUTRAL_COLOR, 2)
        return frame, bboxes, scores

    def get_distance_status(self, bbox: dict, frame_height: int) -> str:
        _, _, _, h = bbox["bbox"]
        ratio = h / frame_height
        if ratio < MIN_FACE_DISTANCE:
            return "TOO_FAR"
        elif ratio > MAX_FACE_DISTANCE:
            return "TOO_CLOSE"
        return "OK"

    def align_face(self, frame: np.ndarray, bbox: dict) -> np.ndarray:
        x, y, w, h = bbox["bbox"]
        x, y = max(0, x), max(0, y)
        cropped = frame[y:y+h, x:x+w]
        return cv2.resize(cropped, (150, 150))

    def get_face_encoding(self, frame: np.ndarray, bbox: dict) -> np.ndarray | None:
        x, y, w, h = bbox["bbox"]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        location = [(y, x + w, y + h, x)]
        encodings = face_recognition.face_encodings(rgb, location)
        return encodings[0] if encodings else None

    def match_with_database(self, face_encoding: np.ndarray) -> tuple[bool, dict | None]:
        if not self.encodings_db:
            return False, None
        known = [e["encoding"] for e in self.encodings_db]
        results = face_recognition.compare_faces(known, face_encoding, tolerance=FACE_MATCH_TOLERANCE)
        if True in results:
            idx = results.index(True)
            return True, self.encodings_db[idx]["employee"]
        return False, None
