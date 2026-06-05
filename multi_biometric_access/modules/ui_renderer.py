"""
Module vẽ toàn bộ giao diện người dùng lên frame OpenCV.
Dùng PIL thay vì cv2.putText để hỗ trợ hiển thị ký tự CJK (tiếng Trung, tiếng Việt có dấu).
在 OpenCV 畫面上繪製完整使用者介面的模組。
使用 PIL 而非 cv2.putText，以支援顯示 CJK 字元（中文、帶聲調越南文）。
"""

import cv2
import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont
from config import SUCCESS_COLOR, FAIL_COLOR, NEUTRAL_COLOR

class UIRenderer:
    """
    Chịu trách nhiệm toàn bộ việc vẽ overlay lên frame — tách biệt logic hiển thị khỏi logic nghiệp vụ.
    負責在畫面上繪製所有視覺疊加層，將顯示邏輯與業務邏輯分離。
    """

    def __init__(self):
        self._blink_counter: int = 0
        self._blink_state: bool = True
        self._font_cache: dict = {}  # Cache font đã tải — tránh đọc file mỗi frame / 快取已載入的字型，避免每幀重複讀取檔案

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        Tìm font CJK có sẵn trên hệ thống theo danh sách ưu tiên.
        Fallback về font mặc định của PIL nếu không tìm thấy font CJK nào.
        按優先順序在系統中尋找可用的 CJK 字型。
        若找不到任何 CJK 字型，則回退至 PIL 的預設字型。
        """
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
        """
        Vẽ văn bản CJK lên PIL canvas — chuyển màu BGR (OpenCV) sang RGB (PIL) trước khi vẽ.
        在 PIL 畫布上繪製 CJK 文字，繪製前先將 BGR（OpenCV）轉換為 RGB（PIL）色彩格式。
        """
        # color là BGR; PIL cần RGB / color 為 BGR 格式；PIL 需要 RGB 格式
        draw.text(pos, text, font=self._load_font(font_size),
                  fill=(color[2], color[1], color[0]))

    def _overlay(
        self, frame: np.ndarray, x: int, y: int, w: int, h: int,
        color: tuple[int, int, int], alpha: float
    ) -> np.ndarray:
        """
        Vẽ hình chữ nhật bán trong suốt bằng cách blend hai bản sao frame.
        Kỹ thuật này tạo cảm giác depth mà không làm mờ nội dung bên dưới hoàn toàn.
        透過混合兩個畫面副本繪製半透明矩形。
        此技術創造層次感，同時不完全遮蓋底層內容。
        """
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    def draw_status_panel(
        self, frame: np.ndarray, state: str, employee: dict | None
    ) -> np.ndarray:
        """
        Vẽ panel trạng thái góc trên-trái: tên state, tên nhân viên (nếu có), và đồng hồ.
        Nền tối bán trong suốt giúp chữ đọc được trên mọi nền camera.
        在左上角繪製狀態面板：狀態名稱、員工姓名（若有）及時鐘。
        半透明深色背景確保文字在任何攝影機背景下都清晰可讀。
        """
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
        """
        Vẽ bounding box khuôn mặt với màu sắc phản ánh trạng thái xác thực.
        Khi FAIL: nhấp nháy bằng cách đổi giữa đỏ và đen theo chu kỳ 30 frame.
        以反映驗證狀態的顏色繪製臉部邊界框。
        FAIL 狀態時：以 30 幀為週期在紅色與黑色之間閃爍。
        """
        x, y, w, h = bbox["bbox"]
        self._blink_counter = (self._blink_counter + 1) % 30
        if status == "SUCCESS":
            color = SUCCESS_COLOR
            thickness = 3
        elif status == "FAIL":
            # Nhấp nháy 15 frame đỏ / 15 frame tắt / 15 幀紅色，15 幀熄滅，循環閃爍
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
        """
        Vẽ thông báo văn bản CJK tại vị trí tuỳ chỉnh — dùng cho hướng dẫn người dùng.
        在指定位置繪製 CJK 文字訊息，用於顯示使用者操作指引。
        """
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, text, pos, 26, NEUTRAL_COLOR)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # Nhãn hiển thị tương ứng với từng state trong state machine / 狀態機各狀態對應的顯示標籤
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

    # Nhãn hiển thị cho từng loại thử thách liveness / 各種活體挑戰的顯示標籤
    _LABELS = {
        "BLINK":      "請眨眼",
        "OPEN_MOUTH": "請張嘴",
        "TURN_LEFT":  "請向左轉頭",
    }

    def draw_card_zone(
        self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
        card_detected: bool
    ) -> np.ndarray:
        """
        Tối hoá vùng ngoài card zone để hướng dẫn người dùng đặt thẻ đúng chỗ.
        Vẽ dấu góc chữ L thay vì khung đầy đủ — ít rối mắt hơn nhưng vẫn định hướng được.
        將卡片區域外的部分調暗，引導使用者將卡片放置於正確位置。
        繪製 L 形角標而非完整邊框，視覺上更簡潔但仍能有效定位。
        """
        color = SUCCESS_COLOR if card_detected else NEUTRAL_COLOR
        # Làm tối vùng ngoài card zone xuống 40% độ sáng để tạo focus / 將卡片區域外的亮度降至 40%，創造視覺焦點
        mask = np.zeros_like(frame)
        mask[:y1, :] = 1
        mask[y2:, :] = 1
        mask[y1:y2, :x1] = 1
        mask[y1:y2, x2:] = 1
        frame = np.where(mask.astype(bool), (frame * 0.4).astype(np.uint8), frame)
        # Vẽ 4 dấu góc L (dài 40px, dày 4px) thay vì khung đầy đủ / 繪製 4 個 L 形角標（長 40px、寬 4px）取代完整邊框
        L = 40
        T = 4
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        dirs = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
        for (cx, cy), (dx, dy) in zip(corners, dirs):
            cv2.line(frame, (cx, cy), (cx + dx * L, cy), color, T)
            cv2.line(frame, (cx, cy), (cx, cy + dy * L), color, T)
        # Hướng dẫn bằng văn bản phía dưới card zone / 在卡片區域下方顯示文字操作指引
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        label = "卡已偵測 ✓" if card_detected else "請將員工證放入框內"
        text_color = SUCCESS_COLOR if card_detected else NEUTRAL_COLOR
        self._put_text(draw, label, (x1, y2 + 10), 22, text_color)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def draw_challenge_prompt(
        self, frame: np.ndarray, challenge: str, time_left: float
    ) -> np.ndarray:
        """
        Hiển thị tên thử thách và thanh tiến trình đếm ngược ở giữa frame.
        Thanh tiến trình trực quan giúp người dùng biết còn bao nhiêu thời gian.
        在畫面中央顯示挑戰名稱與倒數計時進度條。
        視覺化進度條讓使用者清楚掌握剩餘時間。
        """
        h, w = frame.shape[:2]
        label = self._LABELS.get(challenge, challenge)
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, f"指令：{label}", (w // 2 - 200, h // 2), 26, NEUTRAL_COLOR)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        # Tính chiều rộng thanh theo tỉ lệ thời gian còn lại / 根據剩餘時間比例計算進度條寬度
        bar_w = min(int((time_left / 10.0) * 400), 400)
        cv2.rectangle(frame, (w // 2 - 200, h // 2 + 42),
                      (w // 2 - 200 + 400, h // 2 + 62), (50, 50, 50), -1)
        cv2.rectangle(frame, (w // 2 - 200, h // 2 + 42),
                      (w // 2 - 200 + bar_w, h // 2 + 62), NEUTRAL_COLOR, -1)
        return frame

    def draw_access_result(
        self, frame: np.ndarray, granted: bool, employee_name: str
    ) -> np.ndarray:
        """
        Phủ toàn màn hình màu xanh (GRANTED) hoặc đỏ (DENIED) với tên nhân viên.
        Hiệu ứng full-screen tạo phản hồi rõ ràng, dễ thấy từ xa.
        以全螢幕綠色（通過）或紅色（拒絕）疊層顯示員工姓名。
        全螢幕效果提供清晰、可遠距辨識的視覺回饋。
        """
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
        """
        Hiển thị ID được OCR đọc ở góc dưới frame — hữu ích khi debug kết quả quét thẻ.
        在畫面左下角顯示 OCR 讀取的 ID，方便除錯卡片掃描結果。
        """
        h = frame.shape[0]
        img = Image.fromarray(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        self._put_text(draw, f"OCR: {extracted_text}", (10, h - 40), 16, NEUTRAL_COLOR)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
