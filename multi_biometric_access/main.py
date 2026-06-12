"""
Điểm vào chính của hệ thống kiểm soát truy cập đa sinh trắc học.
Điều phối state machine: IDLE → FACE_DETECTED → FACE_MATCHED → LIVENESS_CHECK → CARD_SCAN → VERIFYING → GRANTED/DENIED.
多重生物辨識門禁系統的主入口點。
協調狀態機流程：IDLE → FACE_DETECTED → FACE_MATCHED → LIVENESS_CHECK → CARD_SCAN → VERIFYING → GRANTED/DENIED。
"""

import os
import warnings

# Tắt các log không cần thiết để giữ console sạch khi chạy demo / 抑制不必要的函式庫警告，保持示範時主控台整潔
warnings.filterwarnings("ignore", message=".*pkg_resources.*")
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

import cv2
import csv
import re
import time
import threading
import numpy as np
from config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
    NEUTRAL_COLOR, ACCESS_LOG_PATH, CARD_ZONE
)
from modules.face_detector import FaceDetectorModule
from modules.liveness import LivenessDetector
from modules.ocr_scanner import EmployeeCardScanner
from modules.ui_renderer import UIRenderer

def _ocr_matches(ocr_id: str, card_id: str) -> bool:
    """
    So sánh linh hoạt ID từ OCR với card_id trong database để bù cho lỗi nhận dạng ký tự.
    OCR thường nhầm 'W' thành '1', hoặc chỉ đọc được một phần chuỗi — hàm này xử lý các trường hợp đó.
    彈性比對 OCR 識別的 ID 與資料庫中的 card_id，以補償字元辨識錯誤。
    OCR 常將 'W' 誤讀為 '1'，或只讀到部分字串，此函式處理上述情況。
    """
    if not ocr_id or not card_id:
        return False
    o = ocr_id.strip()
    c = card_id.strip()
    if o == c:
        return True
    # Bù lỗi W↔1: OCR hay đọc nhầm chữ 'W' đầu thành số '1' / 補償 W↔1 首字元混淆：OCR 常把 'W' 開頭誤讀為 '1'
    o_norm = ('W' + o[1:]) if o and o[0] == '1' else o
    if o_norm == c:
        return True
    # OCR chỉ đọc được một phần — kiểm tra chuỗi con (ít nhất 6 ký tự để tránh false positive) / OCR 僅讀到部分字串，做子字串比對（至少 6 字元以避免誤判）
    if len(o) >= 6 and o in c:
        return True
    if len(o_norm) >= 6 and o_norm in c:
        return True
    # So sánh chỉ phần số để bỏ qua tiền tố nhiễu từ OCR / 僅比對數字部分，忽略 OCR 產生的雜訊前綴
    c_digits = re.sub(r'\D', '', c)
    o_digits = re.sub(r'\D', '', o)
    if len(c_digits) >= 6 and c_digits in o_digits:
        return True
    if len(o_digits) >= 6 and o_digits in c_digits:
        return True
    return False

# Thứ tự trạng thái thể hiện luồng xác thực một chiều / 狀態順序體現單向驗證流程
STATES = [
    "IDLE", "FACE_DETECTED", "FACE_MATCHED",
    "LIVENESS_CHECK", "CARD_SCAN", "VERIFYING",
    "GRANTED", "DENIED"
]

class AccessControlSystem:
    """
    Hệ thống kiểm soát truy cập tích hợp nhận diện khuôn mặt, liveness detection và OCR thẻ nhân viên.
    Mỗi lần xác thực phải vượt qua đủ ba lớp theo thứ tự — thiếu một lớp là bị từ chối.
    整合臉部辨識、活體偵測與員工證 OCR 的門禁系統。
    每次驗證必須依序通過三個關卡，缺一即拒絕存取。
    """

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
        self._last_encode_time: float = 0.0  # Chặn encode liên tục để tiết kiệm CPU / 限制連續編碼以節省 CPU
        self._init_log()

    def _init_log(self) -> None:
        """
        Tạo file CSV log nếu chưa tồn tại — đảm bảo header luôn có mặt đúng một lần.
        若 CSV 日誌檔不存在則建立，確保標頭列只出現一次。
        """
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
        """
        Ghi lại kết quả mỗi lần xác thực vào CSV để phục vụ kiểm toán an ninh.
        將每次驗證結果寫入 CSV，供安全稽核使用。
        """
        with open(ACCESS_LOG_PATH, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                face_id, liveness_result, ocr_id, final_result
            ])

    def _set_state(self, state: str) -> None:
        """
        Chuyển trạng thái và reset đồng hồ — cho phép các handler dùng thời gian trong state làm trigger.
        切換狀態並重置計時器，讓各狀態處理器可以用在狀態內的時間作為觸發條件。
        """
        self.state = state
        self.state_entered_at = time.time()

    def _time_in_state(self) -> float:
        """
        Trả về số giây đã trải qua kể từ khi vào trạng thái hiện tại.
        回傳自進入目前狀態以來所經過的秒數。
        """
        return time.time() - self.state_entered_at

    def _get_card_zone_px(self, frame: np.ndarray) -> tuple[int, int, int, int]:
        """
        Chuyển CARD_ZONE từ tỉ lệ sang pixel thực tế — cần thiết vì độ phân giải có thể thay đổi.
        將 CARD_ZONE 從比例轉換為實際像素座標，因為解析度可能不固定。
        """
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = CARD_ZONE
        return int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)

    def _run_ocr_async(self, frame: np.ndarray, zone: tuple[int, int, int, int] | None = None) -> None:
        """
        Chạy OCR trong thread riêng để không chặn vòng lặp webcam chính.
        Kết quả được ghi vào self._ocr_result khi hoàn thành; self._ocr_running đánh dấu trạng thái.
        在獨立執行緒中執行 OCR，避免阻塞主要的攝影機迴圈。
        完成後將結果寫入 self._ocr_result；self._ocr_running 標記執行狀態。
        """
        f = frame.copy()
        _, employee_id = self.card_scanner.scan_card(f, zone)
        try:
            x1, y1, x2, y2 = zone if zone else (
                int(f.shape[1]*0.15), int(f.shape[0]*0.5),
                int(f.shape[1]*0.85), f.shape[0]
            )
            crop = f[y1:y2, x1:x2]
            raw, _ = self.card_scanner.extract_id(
                self.card_scanner.preprocess_for_ocr(crop)
            )
            # Lưu ảnh crop và preprocessed để debug khi OCR thất bại / 儲存裁切與預處理影像，供 OCR 失敗時除錯
            import cv2 as _cv2
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
        """
        Từ chối xử lý frame quá tối — ánh sáng yếu làm face detection và OCR kém chính xác.
        拒絕處理過暗的畫面，因為光線不足會使臉部偵測與 OCR 準確度下降。
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) >= 50.0

    def run(self) -> None:
        """
        Vòng lặp chính: đọc webcam, kiểm tra ánh sáng, xử lý frame qua state machine và hiển thị kết quả.
        主迴圈：讀取攝影機畫面、檢查亮度、透過狀態機處理畫面並顯示結果。
        """
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if not self._check_brightness(frame):
                # Bỏ qua xử lý nặng khi thiếu sáng, chỉ hiển thị cảnh báo / 光線不足時跳過複雜處理，僅顯示警告訊息
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
        """
        Router của state machine — chuyển frame đến đúng handler theo trạng thái hiện tại.
        狀態機的路由器，根據目前狀態將畫面分派至對應的處理器。
        """
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
        """
        Trạng thái chờ — chỉ chuyển sang FACE_DETECTED khi có khuôn mặt xuất hiện trong frame.
        待機狀態，僅在畫面中偵測到人臉時才切換至 FACE_DETECTED。
        """
        frame, bboxes, _ = self.face_detector.detect(frame)
        if bboxes:
            self._set_state("FACE_DETECTED")
        return frame

    def _handle_face_detected(self, frame: np.ndarray) -> np.ndarray:
        """
        Kiểm tra khoảng cách khuôn mặt trước khi mã hoá — tránh lãng phí CPU khi ảnh không đủ chất lượng.
        Throttle 1.5 giây giữa các lần encode để giảm tải xử lý.
        在編碼前先檢查臉部距離，避免對品質不佳的畫面浪費 CPU。
        每次編碼間隔節流 1.5 秒以降低處理負擔。
        """
        frame, bboxes, _ = self.face_detector.detect(frame)
        if not bboxes:
            self._set_state("IDLE")
            return frame

        # 處理最大（最近）的人臉 / 處理最大（最近）的臉部
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
                        self.liveness.reset()  # Tạo bộ thử thách ngẫu nhiên mới / 產生新的隨機挑戰組合
                        self._set_state("FACE_MATCHED")
                    else:
                        self._log("UNKNOWN", "-", "-", "DENIED_NO_MATCH")
                        self._set_state("DENIED")

        frame = self.ui.draw_face_box(frame, biggest, "PROCESSING")
        return frame

    def _handle_face_matched(self, frame: np.ndarray) -> np.ndarray:
        """
        Hiển thị xác nhận khớp khuôn mặt trong 1 giây trước khi chuyển sang liveness — tạo phản hồi thị giác rõ ràng.
        在切換至活體偵測前顯示臉部比對確認 1 秒，提供明確的視覺回饋。
        """
        frame, bboxes, _ = self.face_detector.detect(frame)
        if bboxes:
            biggest = max(bboxes, key=lambda b: b["bbox"][2] * b["bbox"][3])
            frame = self.ui.draw_face_box(frame, biggest, "SUCCESS")
        if self._time_in_state() >= 1.0:
            self._set_state("LIVENESS_CHECK")
        return frame

    def _handle_liveness(self, frame: np.ndarray) -> np.ndarray:
        """
        Chạy thử thách liveness — nếu timeout thì từ chối ngay để tránh bị giữ mãi ở bước này.
        執行活體挑戰；若逾時則立即拒絕，避免系統卡在此步驟。
        """
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
        """
        Thời gian đã trôi qua kể từ khi bắt đầu thử thách liveness — dùng để vẽ thanh đếm ngược.
        自活體挑戰開始以來已過去的時間，用於繪製倒數計時進度條。
        """
        return time.time() - self.liveness.start_time

    def _handle_card_scan(self, frame: np.ndarray) -> np.ndarray:
        """
        Hiển thị vùng quét thẻ và kích hoạt OCR bất đồng bộ sau 2 giây ổn định.
        Kiểm tra token liveness còn hiệu lực để ngăn quét thẻ sau khi phiên hết hạn.
        顯示刷卡區域並在穩定 2 秒後觸發非同步 OCR。
        驗證活體令牌是否有效，防止在工作階段過期後仍可刷卡。
        """
        if not self.liveness.is_token_valid():
            # Token hết hạn — bắt đầu lại từ đầu để đảm bảo an toàn / 令牌過期，重新開始以確保安全
            self._set_state("IDLE")
            return frame

        zone = self._get_card_zone_px(frame)
        x1, y1, x2, y2 = zone
        zone_crop = frame[y1:y2, x1:x2]
        _, card_region = self.card_scanner.detect_card_region(zone_crop)
        card_detected = card_region is not None

        frame = self.ui.draw_card_zone(frame, x1, y1, x2, y2, card_detected)

        if self._ocr_result is not None:
            # OCR đã hoàn thành trong thread nền — chuyển sang xác minh ngay / OCR 已在背景執行緒完成，立即切換至驗證
            self._set_state("VERIFYING")
            return frame

        if not self._ocr_running:
            if self._time_in_state() > 7.0:
                # Hết thời gian quét — thử lại một lần, sau đó từ chối / 掃描超時，重試一次後拒絕存取
                if self.ocr_attempts < 1:
                    self.ocr_attempts += 1
                    self._set_state("CARD_SCAN")
                else:
                    emp_id = self.current_employee.get("id", "") if self.current_employee else ""
                    self._log(emp_id, "PASS", "NONE", "DENIED_OCR_FAIL")
                    self._set_state("DENIED")
            elif self._time_in_state() >= 2.0:
                # Đợi 2 giây để ảnh ổn định trước khi OCR / 等待 2 秒讓畫面穩定後再執行 OCR
                self._ocr_running = True
                t = threading.Thread(
                    target=self._run_ocr_async, args=(frame, zone), daemon=True
                )
                t.start()
        return frame

    def _handle_verifying(self, frame: np.ndarray) -> np.ndarray:
        """
        So sánh ID từ OCR với card_id của nhân viên đã nhận diện — quyết định GRANTED hoặc DENIED.
        將 OCR 取得的 ID 與已辨識員工的 card_id 進行比對，決定授予或拒絕存取。
        """
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
        """
        Hiển thị kết quả cuối 3 giây rồi reset về IDLE — sẵn sàng cho người dùng tiếp theo.
        顯示最終結果 3 秒後重置至 IDLE，為下一位使用者做好準備。
        """
        granted = self.state == "GRANTED"
        name = self.current_employee.get("name", "") if self.current_employee else ""
        frame = self.ui.draw_access_result(frame, granted, name)

        if self._time_in_state() > 3.0:
            # Xoá toàn bộ context của phiên hiện tại trước khi bắt đầu phiên mới / 在開始新工作階段前清除所有目前工作階段的狀態
            self.current_employee = None
            self.liveness.reset()
            self._ocr_result = None
            self._ocr_running = False
            self._set_state("IDLE")
        return frame


if __name__ == "__main__":
    from data_sync import sync_employee_data
    sync_employee_data()

    system = AccessControlSystem()
    system.run()
