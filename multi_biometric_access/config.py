"""
Tập trung toàn bộ tham số cấu hình hệ thống vào một nơi để dễ điều chỉnh mà không cần sửa logic.
將所有系統配置參數集中於此，方便調整而無需修改業務邏輯。
"""

import os

_BASE = os.path.dirname(os.path.abspath(__file__))

CAMERA_INDEX = 0                    # Chỉ số camera (0 = webcam mặc định) / 攝影機索引（0 = 預設網路攝影機）
FRAME_WIDTH, FRAME_HEIGHT = 1280, 720  # Độ phân giải khung hình — ảnh hưởng đến FPS và chất lượng OCR / 畫面解析度，影響 FPS 與 OCR 品質

MIN_FACE_DISTANCE = 0.3             # Tỉ lệ chiều cao khuôn mặt / frame tối thiểu — dưới ngưỡng này là quá xa / 臉部高度與畫面比例下限，低於此為距離過遠
MAX_FACE_DISTANCE = 0.8             # Tỉ lệ tối đa — vượt quá này là quá gần, có thể gây mất góc nhìn / 比例上限，超過則距離過近，可能導致視角不完整

LIVENESS_TIMEOUT = 10               # Thời gian tối đa (giây) để hoàn thành thử thách liveness / 完成活體挑戰的最長時間（秒）
OCR_CONFIDENCE_THRESHOLD = 20       # Điểm tin cậy tối thiểu của Tesseract để chấp nhận một token / Tesseract 接受字元的最低信心分數

EMPLOYEE_DB_PATH = os.path.join(_BASE, "data", "employees.json")    # Cơ sở dữ liệu nhân viên (JSON) / 員工資料庫（JSON 格式）
FACE_ENCODINGS_PATH = os.path.join(_BASE, "data", "face_encodings.pkl")  # Encodings khuôn mặt đã tiền xử lý (pickle) / 預先計算的臉部特徵向量（pickle 格式）

FACE_MATCH_TOLERANCE = 0.43         # Ngưỡng khoảng cách Euclidean — nhỏ hơn = khớp; giá trị thấp hơn nghiêm ngặt hơn / 歐氏距離閾值，越低越嚴格；低於此值視為人臉相符

CARD_ZONE = (0.22, 0.036, 0.78, 0.664)  # Vùng đặt thẻ nhân viên — tỉ lệ (x1, y1, x2, y2) so với kích thước frame, theo tỉ lệ thẻ ISO/CR80 85.6x53.98mm (~1.586:1) / 員工證放置區域，以畫面寬高比例表示 (x1, y1, x2, y2)，符合 ISO/CR80 卡片比例 85.6x53.98mm (~1.586:1)

SUCCESS_COLOR = (0, 255, 0)         # Màu xanh lá — hiển thị khi xác thực thành công / 綠色，用於認證成功的視覺回饋
FAIL_COLOR = (0, 0, 255)            # Màu đỏ — hiển thị khi từ chối truy cập / 紅色，用於拒絕存取的視覺回饋
NEUTRAL_COLOR = (255, 200, 0)       # Màu vàng — hướng dẫn người dùng trong quá trình xác thực / 黃色，用於引導使用者進行驗證流程

ACCESS_LOG_PATH = os.path.join(_BASE, "access_log.csv")  # File ghi lại mọi sự kiện ra/vào cho kiểm toán / 記錄所有進出事件的稽核日誌檔案
