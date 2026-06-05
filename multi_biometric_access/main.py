import cv2
import csv
import os
import re
import time
import threading
import numpy as np
from config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    NEUTRAL_COLOR, ACCESS_LOG_PATH
)
from modules.face_detector import FaceDetectorModule
from modules.liveness import LivenessDetector
from modules.ocr_scanner import EmployeeCardScanner
from modules.ui_renderer import UIRenderer

def _ocr_matches(ocr_id: str, card_id: str) -> bool:
    if not ocr_id or not card_id:
        return False
    o = ocr_id.strip()
    c = card_id.strip()
    if o == c:
        return True
    # Allow W<->1 prefix swap
    o_norm = ('W' + o[1:]) if o and o[0] == '1' else o
    if o_norm == c:
        return True
    # Substring: OCR result (min 6 chars) appears in card_id (handles partial reads)
    if len(o) >= 6 and o in c:
        return True
    if len(o_norm) >= 6 and o_norm in c:
        return True
    # Reverse: card_id digits appear in OCR (OCR may have added noise prefix)
    c_digits = re.sub(r'\D', '', c)
    o_digits = re.sub(r'\D', '', o)
    if len(c_digits) >= 6 and c_digits in o_digits:
        return True
    if len(o_digits) >= 6 and o_digits in c_digits:
        return True
    return False

STATES = [
    "IDLE", "FACE_DETECTED", "FACE_MATCHED",
    "LIVENESS_CHECK", "CARD_SCAN", "VERIFYING",
    "GRANTED", "DENIED"
]

class AccessControlSystem:
    def __init__(self) -> None:
        self.face_detector = FaceDetectorModule()
        self.liveness = LivenessDetector()
        self.card_scanner = EmployeeCardScanner()
        self.ui = UIRenderer()

        self.state: str = "IDLE"
        self.current_employee: dict | None = None
        self.state_entered_at: float = time.time()
        self.ocr_attempts: int = 0
        self._ocr_result: str | None = None
        self._ocr_running: bool = False
        self._last_encode_time: float = 0.0
        self._init_log()

    def _init_log(self) -> None:
        if not os.path.exists(ACCESS_LOG_PATH):
            with open(ACCESS_LOG_PATH, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "face_id", "liveness_result",
                    "ocr_id", "final_result"
                ])

    def _log(
        self, face_id: str, liveness_result: str,
        ocr_id: str, final_result: str
    ) -> None:
        with open(ACCESS_LOG_PATH, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                face_id, liveness_result, ocr_id, final_result
            ])

    def _set_state(self, state: str) -> None:
        self.state = state
        self.state_entered_at = time.time()

    def _time_in_state(self) -> float:
        return time.time() - self.state_entered_at

    def _run_ocr_async(self, frame: np.ndarray) -> None:
        f = frame.copy()
        _, employee_id = self.card_scanner.scan_card(f)
        # Debug: log raw OCR text to /tmp/ocr_debug.txt
        try:
            raw, _ = self.card_scanner.extract_id(
                self.card_scanner.preprocess_for_ocr(
                    f[int(f.shape[0]*0.5):, int(f.shape[1]*0.15):int(f.shape[1]*0.85)]
                )
            )
            import cv2 as _cv2
            h, w = f.shape[:2]
            crop = f[int(h*0.5):h, int(w*0.15):int(w*0.85)]
            _cv2.imwrite("/tmp/ocr_crop.jpg", crop)
            _cv2.imwrite("/tmp/ocr_preprocessed.jpg",
                self.card_scanner.preprocess_for_ocr(crop))
            with open("/tmp/ocr_debug.txt", "w") as dbg:
                dbg.write(f"employee_id: {employee_id}\nraw_text: {raw}\n")
        except Exception:
            pass
        self._ocr_result = employee_id
        self._ocr_running = False

    def _check_brightness(self, frame: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) >= 50.0

    def run(self) -> None:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if not self._check_brightness(frame):
                frame = self.ui.draw_message(frame, "光線不足！", (50, 50))
                cv2.imshow("Access Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            frame = self._process(frame)
            cv2.imshow("Access Control", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

    def _process(self, frame: np.ndarray) -> np.ndarray:
        if self.state == "IDLE":
            frame = self._handle_idle(frame)
        elif self.state == "FACE_DETECTED":
            frame = self._handle_face_detected(frame)
        elif self.state == "FACE_MATCHED":
            frame = self._handle_face_matched(frame)
        elif self.state == "LIVENESS_CHECK":
            frame = self._handle_liveness(frame)
        elif self.state == "CARD_SCAN":
            frame = self._handle_card_scan(frame)
        elif self.state == "VERIFYING":
            frame = self._handle_verifying(frame)
        elif self.state in ("GRANTED", "DENIED"):
            frame = self._handle_terminal(frame)

        frame = self.ui.draw_status_panel(frame, self.state, self.current_employee)
        return frame

    def _handle_idle(self, frame: np.ndarray) -> np.ndarray:
        frame, bboxes, _ = self.face_detector.detect(frame)
        if bboxes:
            self._set_state("FACE_DETECTED")
        return frame

    def _handle_face_detected(self, frame: np.ndarray) -> np.ndarray:
        frame, bboxes, _ = self.face_detector.detect(frame)
        if not bboxes:
            self._set_state("IDLE")
            return frame

        # 處理最大（最近）的人臉
        biggest = max(bboxes, key=lambda b: b["bbox"][2] * b["bbox"][3])
        status = self.face_detector.get_distance_status(biggest, frame.shape[0])

        if status == "TOO_FAR":
            frame = self.ui.draw_message(frame, "請靠近鏡頭", (50, frame.shape[0] - 60))
        elif status == "TOO_CLOSE":
            frame = self.ui.draw_message(frame, "請退後一些", (50, frame.shape[0] - 60))
        else:
            now = time.time()
            if now - self._last_encode_time >= 1.5:
                self._last_encode_time = now
                encoding = self.face_detector.get_face_encoding(frame, biggest)
                if encoding is not None:
                    matched, employee = self.face_detector.match_with_database(encoding)
                    if matched:
                        self.current_employee = employee
                        self.liveness.reset()
                        self._set_state("FACE_MATCHED")
                    else:
                        self._log("UNKNOWN", "-", "-", "DENIED_NO_MATCH")
                        self._set_state("DENIED")

        frame = self.ui.draw_face_box(frame, biggest, "PROCESSING")
        return frame

    def _handle_face_matched(self, frame: np.ndarray) -> np.ndarray:
        frame, bboxes, _ = self.face_detector.detect(frame)
        if bboxes:
            biggest = max(bboxes, key=lambda b: b["bbox"][2] * b["bbox"][3])
            frame = self.ui.draw_face_box(frame, biggest, "SUCCESS")
        if self._time_in_state() >= 1.0:
            self._set_state("LIVENESS_CHECK")
        return frame

    def _handle_liveness(self, frame: np.ndarray) -> np.ndarray:
        frame, done, challenge = self.liveness.run_challenge(frame)

        if challenge == "TIMEOUT":
            emp_id = self.current_employee.get("id", "") if self.current_employee else ""
            self._log(emp_id, "LIVENESS_TIMEOUT", "-", "DENIED")
            self.current_employee = None
            self._set_state("DENIED")
            return frame

        time_left = max(0.0, 10.0 - self.liveness_elapsed())
        frame = self.ui.draw_challenge_prompt(frame, challenge, time_left)

        if done:
            self.ocr_attempts = 0
            self._set_state("CARD_SCAN")
        return frame

    def liveness_elapsed(self) -> float:
        return time.time() - self.liveness.start_time

    def _handle_card_scan(self, frame: np.ndarray) -> np.ndarray:
        if not self.liveness.is_token_valid():
            self._set_state("IDLE")
            return frame

        frame = self.ui.draw_message(frame, "請出示員工證", (50, frame.shape[0] - 60))

        if self._ocr_result is not None:
            self._set_state("VERIFYING")
            return frame

        if not self._ocr_running:
            if self._time_in_state() > 7.0:
                if self.ocr_attempts < 1:
                    self.ocr_attempts += 1
                    self._set_state("CARD_SCAN")
                else:
                    emp_id = self.current_employee.get("id", "") if self.current_employee else ""
                    self._log(emp_id, "PASS", "NONE", "DENIED_OCR_FAIL")
                    self._set_state("DENIED")
            elif self._time_in_state() >= 2.0:
                self._ocr_running = True
                t = threading.Thread(target=self._run_ocr_async, args=(frame,), daemon=True)
                t.start()
        return frame

    def _handle_verifying(self, frame: np.ndarray) -> np.ndarray:
        ocr_id = self._ocr_result
        emp_id = self.current_employee.get("card_id", "") if self.current_employee else ""

        if _ocr_matches(ocr_id or "", emp_id):
            self._log(emp_id, "PASS", ocr_id, "GRANTED")
            self._set_state("GRANTED")
        else:
            self._log(emp_id, "PASS", ocr_id or "", "DENIED_ID_MISMATCH")
            self._set_state("DENIED")

        frame = self.ui.draw_ocr_overlay(frame, ocr_id or "")
        return frame

    def _handle_terminal(self, frame: np.ndarray) -> np.ndarray:
        granted = self.state == "GRANTED"
        name = self.current_employee.get("name", "") if self.current_employee else ""
        frame = self.ui.draw_access_result(frame, granted, name)

        if self._time_in_state() > 3.0:
            self.current_employee = None
            self.liveness.reset()
            self._ocr_result = None
            self._ocr_running = False
            self._set_state("IDLE")
        return frame


if __name__ == "__main__":
    system = AccessControlSystem()
    system.run()
