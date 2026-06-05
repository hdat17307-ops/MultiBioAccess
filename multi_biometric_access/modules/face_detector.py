"""
Module phát hiện và nhận diện khuôn mặt dựa trên thư viện face_recognition.
Phân biệt rõ ba bước: detect (tìm vị trí) → encode (trích đặc trưng) → match (so sánh với database).
基於 face_recognition 函式庫的臉部偵測與辨識模組。
明確區分三個步驟：detect（定位）→ encode（提取特徵）→ match（與資料庫比對）。
"""

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
    """
    Bao gồm toàn bộ pipeline nhận diện khuôn mặt từ raw frame đến kết quả khớp với database.
    封裝從原始畫面到資料庫比對結果的完整臉部辨識流程。
    """

    def __init__(self) -> None:
        # Tải encodings một lần khi khởi động — tránh đọc file mỗi frame / 啟動時載入一次特徵向量，避免每幀都讀取檔案
        self.encodings_db: list[dict] = self._load_encodings()

    def _load_encodings(self) -> list[dict]:
        """
        Nạp dữ liệu encodings đã được tiền xử lý bởi setup_db.py.
        Trả về list rỗng nếu file chưa tồn tại để tránh crash khi chưa chạy setup.
        載入由 setup_db.py 預先計算的臉部特徵向量。
        若檔案不存在則回傳空列表，避免未執行初始化時系統崩潰。
        """
        if os.path.exists(FACE_ENCODINGS_PATH):
            with open(FACE_ENCODINGS_PATH, "rb") as f:
                return pickle.load(f)
        return []

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, list, list]:
        """
        Phát hiện vị trí khuôn mặt trong frame bằng HOG — nhanh hơn CNN, đủ dùng cho real-time.
        Vẽ bounding box lên frame để người dùng thấy hệ thống đang theo dõi ai.
        使用 HOG 模型偵測畫面中的臉部位置，比 CNN 更快，足以應付即時處理。
        在畫面上繪製邊界框，讓使用者了解系統正在追蹤的對象。
        """
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
        """
        Đánh giá khoảng cách dựa trên tỉ lệ chiều cao khuôn mặt trên frame.
        Khuôn mặt quá nhỏ hay quá lớn đều làm encoding kém chính xác.
        根據臉部高度與畫面高度的比例評估距離。
        臉部過小或過大都會降低特徵編碼的準確度。
        """
        _, _, _, h = bbox["bbox"]
        ratio = h / frame_height
        if ratio < MIN_FACE_DISTANCE:
            return "TOO_FAR"
        elif ratio > MAX_FACE_DISTANCE:
            return "TOO_CLOSE"
        return "OK"

    def align_face(self, frame: np.ndarray, bbox: dict) -> np.ndarray:
        """
        Cắt và resize khuôn mặt về kích thước chuẩn 150x150 — dùng để hiển thị thumbnail.
        裁切並縮放臉部至標準 150x150 尺寸，用於顯示縮圖。
        """
        x, y, w, h = bbox["bbox"]
        x, y = max(0, x), max(0, y)
        cropped = frame[y:y+h, x:x+w]
        return cv2.resize(cropped, (150, 150))

    def get_face_encoding(self, frame: np.ndarray, bbox: dict) -> np.ndarray | None:
        """
        Trích xuất vector đặc trưng 128 chiều từ vùng khuôn mặt đã biết vị trí.
        Truyền location trực tiếp thay vì để face_recognition tìm lại — tiết kiệm thời gian.
        從已知位置的臉部區域提取 128 維特徵向量。
        直接傳入位置座標而非讓函式庫重新搜尋，以節省運算時間。
        """
        x, y, w, h = bbox["bbox"]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        location = [(y, x + w, y + h, x)]
        encodings = face_recognition.face_encodings(rgb, location)
        return encodings[0] if encodings else None

    def match_with_database(self, face_encoding: np.ndarray) -> tuple[bool, dict | None]:
        """
        So sánh encoding với toàn bộ database bằng face_distance thay vì compare_faces.
        face_distance trả về giá trị liên tục nên chọn được người khớp nhất, không chỉ True/False.
        使用 face_distance 而非 compare_faces 將特徵向量與整個資料庫進行比對。
        face_distance 回傳連續數值，可選出最相符者，而非僅得到是/否結果。
        """
        if not self.encodings_db:
            return False, None
        known = [e["encoding"] for e in self.encodings_db]
        try:
            distances = face_recognition.face_distance(known, face_encoding)
            idx = int(np.argmin(distances))  # Chỉ số của người khớp nhất / 最相符者的索引
        except Exception:
            return False, None
        if distances[idx] <= FACE_MATCH_TOLERANCE:
            return True, self.encodings_db[idx]["employee"]
        return False, None
