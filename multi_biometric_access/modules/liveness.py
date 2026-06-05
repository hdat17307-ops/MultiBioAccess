"""
Module chống giả mạo bằng cơ chế thử thách-phản hồi (challenge-response).
Yêu cầu người dùng thực hiện hành động ngẫu nhiên để phân biệt người thật với ảnh tĩnh hoặc video.
以挑戰-回應機制防止欺騙攻擊的模組。
要求使用者執行隨機動作，以區分真人與靜態照片或影片。
"""

import cv2
import numpy as np
import time
import random
import os
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from config import LIVENESS_TIMEOUT

# Tập hành động có thể được chọn ngẫu nhiên — đa dạng để khó đoán / 可隨機選取的動作集合，多樣化以增加難以預測性
CHALLENGES = ["BLINK", "OPEN_MOUTH", "TURN_LEFT"]
CHALLENGE_LABELS = {
    "BLINK":      "請眨眼",
    "OPEN_MOUTH": "請張嘴",
    "TURN_LEFT":  "請向左轉頭",
}

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "face_landmarker.task")

class LivenessDetector:
    """
    Phát hiện liveness qua hai thử thách ngẫu nhiên mỗi phiên.
    Dùng MediaPipe Face Landmarker để lấy 478 landmark điểm khuôn mặt chính xác cao.
    透過每個工作階段的兩個隨機挑戰進行活體偵測。
    使用 MediaPipe Face Landmarker 取得高精度的 478 個臉部標記點。
    """

    def __init__(self) -> None:
        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            # Tắt blendshapes và transform matrix vì không dùng — giảm overhead / 關閉未使用的混合形狀與變換矩陣以降低運算負擔
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self.challenges: list[str] = []
        self.current_idx: int = 0
        self.start_time: float = 0.0
        self.completed: bool = False
        self.completion_time: float = 0.0
        self.TOKEN_TTL = 30  # Token liveness hết hiệu lực sau 30 giây để buộc quét thẻ kịp thời / 活體令牌 30 秒後失效，強制使用者及時刷卡
        self._reset_session()

    def _reset_session(self) -> None:
        """
        Chọn 2 thử thách ngẫu nhiên và reset toàn bộ trạng thái phiên.
        Ngẫu nhiên hoá để kẻ tấn công không thể chuẩn bị video đáp ứng đúng thứ tự cố định.
        隨機選取 2 個挑戰並重置所有工作階段狀態。
        隨機化可防止攻擊者預先準備符合固定順序的影片。
        """
        selected = random.sample(CHALLENGES, 2)
        self.challenges = selected
        self.current_idx = 0
        self.start_time = time.time()
        self.completed = False
        self.completion_time = 0.0

    def reset(self) -> None:
        """
        API công khai để reset phiên — được gọi mỗi khi nhận diện khuôn mặt mới.
        對外公開的重置 API，在每次識別到新臉部時呼叫。
        """
        self._reset_session()

    def is_token_valid(self) -> bool:
        """
        Kiểm tra xem token liveness vẫn còn trong thời hạn TOKEN_TTL.
        Ngăn người dùng hoàn thành liveness rồi chờ lâu mới quét thẻ.
        檢查活體令牌是否仍在 TOKEN_TTL 有效期內。
        防止使用者完成活體驗證後等待過久才刷卡。
        """
        if not self.completed:
            return False
        return time.time() - self.completion_time < self.TOKEN_TTL

    def _get_landmarks(self, frame: np.ndarray) -> list | None:
        """
        Chạy MediaPipe landmarker và chuyển toạ độ chuẩn hoá (0–1) về pixel thực.
        Trả về None nếu không có khuôn mặt để caller xử lý an toàn.
        執行 MediaPipe 標記器，將正規化座標（0–1）轉換為實際像素座標。
        若未偵測到臉部則回傳 None，讓呼叫端安全處理。
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        h, w = frame.shape[:2]
        lm = result.face_landmarks[0]
        return [[int(p.x * w), int(p.y * h)] for p in lm]

    def detect_blink(self, landmarks: list) -> bool:
        """
        Tính EAR (Eye Aspect Ratio): tỉ lệ chiều dọc / chiều ngang của mắt.
        EAR < 0.2 cho thấy mắt đang nhắm — đây là dấu hiệu chớp mắt.
        計算 EAR（眼睛長寬比）：眼睛垂直距離與水平距離的比值。
        EAR < 0.2 表示眼睛閉合，即偵測到眨眼動作。
        """
        top = np.array(landmarks[159])     # Điểm trên mí mắt / 上眼瞼標記點
        bottom = np.array(landmarks[145])  # Điểm dưới mí mắt / 下眼瞼標記點
        left = np.array(landmarks[33])     # Góc trái của mắt / 眼角左側標記點
        right = np.array(landmarks[133])   # Góc phải của mắt / 眼角右側標記點
        vertical = np.linalg.norm(top - bottom)
        horizontal = np.linalg.norm(left - right)
        if horizontal == 0:
            return False
        return (vertical / horizontal) < 0.2

    def detect_mouth_open(self, landmarks: list) -> bool:
        """
        Tính MAR (Mouth Aspect Ratio): tỉ lệ chiều dọc / chiều ngang của miệng.
        MAR > 0.5 cho thấy miệng đang há đủ rộng để tính là hành động hợp lệ.
        計算 MAR（嘴巴長寬比）：嘴巴垂直距離與水平距離的比值。
        MAR > 0.5 表示嘴巴張開幅度足夠，視為有效動作。
        """
        upper = np.array(landmarks[13])    # Môi trên / 上嘴唇標記點
        lower = np.array(landmarks[14])    # Môi dưới / 下嘴唇標記點
        left = np.array(landmarks[78])     # Góc trái của miệng / 嘴角左側標記點
        right = np.array(landmarks[308])   # Góc phải của miệng / 嘴角右側標記點
        vertical = np.linalg.norm(upper - lower)
        horizontal = np.linalg.norm(left - right)
        if horizontal == 0:
            return False
        return (vertical / horizontal) > 0.5

    def detect_head_turn(self, landmarks: list) -> str:
        """
        Phát hiện hướng quay đầu bằng cách so sánh vị trí mũi với trung tâm khuôn mặt.
        Khi quay trái, mũi dịch sang trái so với tâm — offset âm trên trục X.
        透過比較鼻尖位置與臉部中心來偵測頭部轉向。
        向左轉時，鼻尖相對於臉部中心往左偏移，即 X 軸偏移量為負值。
        """
        if len(landmarks) <= 454:
            return "CENTER"
        nose = np.array(landmarks[1])            # Đỉnh mũi / 鼻尖標記點
        left_cheek = np.array(landmarks[234])    # Má trái / 左臉頰標記點
        right_cheek = np.array(landmarks[454])   # Má phải / 右臉頰標記點
        face_center_x = (left_cheek[0] + right_cheek[0]) / 2
        offset = nose[0] - face_center_x
        face_width = abs(right_cheek[0] - left_cheek[0])
        if face_width == 0:
            return "CENTER"
        # Chuẩn hoá offset theo chiều rộng khuôn mặt để tránh ảnh hưởng của khoảng cách / 以臉部寬度正規化偏移量，避免距離遠近影響判斷
        ratio = offset / face_width
        if ratio < -0.15:
            return "LEFT"
        elif ratio > 0.15:
            return "RIGHT"
        return "CENTER"

    def run_challenge(self, frame: np.ndarray) -> tuple[np.ndarray, bool, str]:
        """
        Xử lý frame theo thử thách hiện tại; trả về (frame, đã_hoàn_thành, tên_thử_thách).
        Khi tất cả thử thách vượt qua, đánh dấu completed và ghi thời điểm để tính TTL token.
        處理目前挑戰的畫面，回傳（畫面, 是否完成, 挑戰名稱）。
        所有挑戰通過後標記完成，並記錄時間點以計算令牌 TTL。
        """
        if self.completed:
            return frame, True, ""

        elapsed = time.time() - self.start_time
        if elapsed > LIVENESS_TIMEOUT:
            # Reset để chuẩn bị cho lần thử tiếp theo / 重置以準備下一次嘗試
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
