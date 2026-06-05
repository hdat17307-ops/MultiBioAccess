import cv2
import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont
from config import SUCCESS_COLOR, FAIL_COLOR, NEUTRAL_COLOR

class UIRenderer:
    def __init__(self):
        self._blink_counter: int = 0
        self._blink_state: bool = True
        self._font_cache: dict = {}

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if size in self._font_cache:
            return self._font_cache[size]
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/google-noto-sans-cjk-vf-fonts/NotoSansCJK-VF.ttc",
            "/usr/share/fonts/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/NotoSansCJKtc-Regular.otf",
            "/usr/share/fonts/wenquanyi/WenQuanYiMicroHei.ttf",
            "/usr/local/share/fonts/WenQuanYiMicroHei.ttf",
        ]
        font = None
        for path in candidates:
            try:
                font = ImageFont.truetype(path, size)
                break
            except (IOError, OSError):
                continue
        if font is None:
            font = ImageFont.load_default()
        self._font_cache[size] = font
        return font

    def _put_text(
        self, draw: ImageDraw.Draw, text: str, pos: tuple[int, int],
        font_size: int, color: tuple[int, int, int]
    ) -> None:
        # color is BGR; PIL needs RGB
        draw.text(pos, text, font=self._load_font(font_size),
                  fill=(color[2], color[1], color[0]))

    def _overlay(
        self, frame: np.ndarray, x: int, y: int, w: int, h: int,
        color: tuple[int, int, int], alpha: float
    ) -> np.ndarray:
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    def draw_status_panel(
        self, frame: np.ndarray, state: str, employee: dict | None
    ) -> np.ndarray:
        frame = self._overlay(frame, 10, 10, 320, 100, (0, 0, 0), 0.5)
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        label = self._STATE_LABELS.get(state, state)
        self._put_text(draw, f"狀態：{label}", (20, 35), 18, (255, 255, 255))
        if employee:
            self._put_text(draw, employee.get("name", ""), (20, 65), 16, SUCCESS_COLOR)
        ts = time.strftime("%H:%M:%S")
        self._put_text(draw, ts, (20, 95), 14, (200, 200, 200))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def draw_face_box(
        self, frame: np.ndarray, bbox: dict, status: str
    ) -> np.ndarray:
        x, y, w, h = bbox["bbox"]
        self._blink_counter = (self._blink_counter + 1) % 30
        if status == "SUCCESS":
            color = SUCCESS_COLOR
            thickness = 3
        elif status == "FAIL":
            self._blink_state = self._blink_counter < 15
            color = FAIL_COLOR if self._blink_state else (0, 0, 0)
            thickness = 3
        else:
            color = NEUTRAL_COLOR
            thickness = 2
        frame = frame.copy()
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
        return frame

    def draw_message(
        self, frame: np.ndarray, text: str, pos: tuple[int, int]
    ) -> np.ndarray:
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, text, pos, 26, NEUTRAL_COLOR)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    _STATE_LABELS = {
        "IDLE":           "待機",
        "FACE_DETECTED":  "偵測到人臉",
        "FACE_MATCHED":   "人臉比對成功",
        "LIVENESS_CHECK": "活體檢測",
        "CARD_SCAN":      "掃描員工證",
        "VERIFYING":      "驗證中",
        "GRANTED":        "存取通過",
        "DENIED":         "存取拒絕",
    }

    _LABELS = {
        "BLINK":      "請眨眼",
        "OPEN_MOUTH": "請張嘴",
        "TURN_LEFT":  "請向左轉頭",
    }

    def draw_challenge_prompt(
        self, frame: np.ndarray, challenge: str, time_left: float
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        label = self._LABELS.get(challenge, challenge)
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, f"指令：{label}", (w // 2 - 200, h // 2), 26, NEUTRAL_COLOR)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        bar_w = min(int((time_left / 10.0) * 400), 400)
        cv2.rectangle(frame, (w // 2 - 200, h // 2 + 42),
                      (w // 2 - 200 + 400, h // 2 + 62), (50, 50, 50), -1)
        cv2.rectangle(frame, (w // 2 - 200, h // 2 + 42),
                      (w // 2 - 200 + bar_w, h // 2 + 62), NEUTRAL_COLOR, -1)
        return frame

    def draw_access_result(
        self, frame: np.ndarray, granted: bool, employee_name: str
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        color = SUCCESS_COLOR if granted else FAIL_COLOR
        frame = self._overlay(frame, 0, 0, w, h, color, 0.4)
        text = "存取已授權" if granted else "存取被拒絕"
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, text, (w // 2 - 280, h // 2), 30, (255, 255, 255))
        if employee_name:
            self._put_text(draw, employee_name, (w // 2 - 100, h // 2 + 50), 22, (255, 255, 255))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def draw_ocr_overlay(
        self, frame: np.ndarray, extracted_text: str
    ) -> np.ndarray:
        h = frame.shape[0]
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, f"OCR: {extracted_text}", (10, h - 40), 16, NEUTRAL_COLOR)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
