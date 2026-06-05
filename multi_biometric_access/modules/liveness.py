import cv2
import numpy as np
import time
import random
import os
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from config import LIVENESS_TIMEOUT

CHALLENGES = ["BLINK", "OPEN_MOUTH", "TURN_LEFT"]
CHALLENGE_LABELS = {
    "BLINK":      "請眨眼",
    "OPEN_MOUTH": "請張嘴",
    "TURN_LEFT":  "請向左轉頭",
}

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "face_landmarker.task")

class LivenessDetector:
    def __init__(self) -> None:
        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self.challenges: list[str] = []
        self.current_idx: int = 0
        self.start_time: float = 0.0
        self.completed: bool = False
        self.completion_time: float = 0.0
        self.TOKEN_TTL = 30
        self._reset_session()

    def _reset_session(self) -> None:
        selected = random.sample(CHALLENGES, 2)
        self.challenges = selected
        self.current_idx = 0
        self.start_time = time.time()
        self.completed = False
        self.completion_time = 0.0

    def reset(self) -> None:
        self._reset_session()

    def is_token_valid(self) -> bool:
        if not self.completed:
            return False
        return time.time() - self.completion_time < self.TOKEN_TTL

    def _get_landmarks(self, frame: np.ndarray) -> list | None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        h, w = frame.shape[:2]
        lm = result.face_landmarks[0]
        return [[int(p.x * w), int(p.y * h)] for p in lm]

    def detect_blink(self, landmarks: list) -> bool:
        top = np.array(landmarks[159])
        bottom = np.array(landmarks[145])
        left = np.array(landmarks[33])
        right = np.array(landmarks[133])
        vertical = np.linalg.norm(top - bottom)
        horizontal = np.linalg.norm(left - right)
        if horizontal == 0:
            return False
        return (vertical / horizontal) < 0.2

    def detect_mouth_open(self, landmarks: list) -> bool:
        upper = np.array(landmarks[13])
        lower = np.array(landmarks[14])
        left = np.array(landmarks[78])
        right = np.array(landmarks[308])
        vertical = np.linalg.norm(upper - lower)
        horizontal = np.linalg.norm(left - right)
        if horizontal == 0:
            return False
        return (vertical / horizontal) > 0.5

    def detect_head_turn(self, landmarks: list) -> str:
        if len(landmarks) <= 454:
            return "CENTER"
        nose = np.array(landmarks[1])
        left_cheek = np.array(landmarks[234])
        right_cheek = np.array(landmarks[454])
        face_center_x = (left_cheek[0] + right_cheek[0]) / 2
        offset = nose[0] - face_center_x
        face_width = abs(right_cheek[0] - left_cheek[0])
        if face_width == 0:
            return "CENTER"
        ratio = offset / face_width
        if ratio < -0.15:
            return "LEFT"
        elif ratio > 0.15:
            return "RIGHT"
        return "CENTER"

    def run_challenge(self, frame: np.ndarray) -> tuple[np.ndarray, bool, str]:
        if self.completed:
            return frame, True, ""

        elapsed = time.time() - self.start_time
        if elapsed > LIVENESS_TIMEOUT:
            self._reset_session()
            return frame, False, "TIMEOUT"

        current_challenge = self.challenges[self.current_idx]
        landmarks = self._get_landmarks(frame)

        if landmarks:
            detected = False
            if current_challenge == "BLINK":
                detected = self.detect_blink(landmarks)
            elif current_challenge == "OPEN_MOUTH":
                detected = self.detect_mouth_open(landmarks)
            elif current_challenge == "TURN_LEFT":
                detected = self.detect_head_turn(landmarks) == "LEFT"

            if detected:
                self.current_idx += 1
                if self.current_idx >= len(self.challenges):
                    self.completed = True
                    self.completion_time = time.time()
                    return frame, True, current_challenge

        return frame, False, current_challenge
