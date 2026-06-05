"""
Module quét và trích xuất ID từ thẻ nhân viên bằng Tesseract OCR.
Xử lý bao gồm: phát hiện vùng thẻ, perspective transform, tăng độ tương phản và lọc regex.
使用 Tesseract OCR 掃描並提取員工證 ID 的模組。
處理流程包含：卡片區域偵測、透視變換、對比度增強與正則表達式過濾。
"""

import cv2
import numpy as np
import pytesseract
import re
from config import OCR_CONFIDENCE_THRESHOLD

class EmployeeCardScanner:
    """
    Quét thẻ nhân viên cầm tay và trả về mã nhân viên — chịu trách nhiệm toàn bộ pipeline OCR.
    掃描手持員工證並回傳員工代碼，負責整個 OCR 流程。
    """

    def __init__(self):
        # PSM 11: chế độ tìm văn bản rải rác — phù hợp khi thẻ chứa nhiều field khác nhau / PSM 11：稀疏文字模式，適用於卡片包含多個不同欄位的情況
        self._ocr_config = "--psm 11 -l eng"
        # Ba pattern theo độ ưu tiên giảm dần: format chuẩn → W-prefix → thuần số / 三個模式按優先順序排列：標準格式 → W 前綴 → 純數字
        self._id_pattern = re.compile(r'[A-Z]{2,3}-?\d{4,6}')   # Ví dụ: EMP-001234 / 例如：EMP-001234
        self._w_pattern = re.compile(r'[A-Za-z]?\d{7,12}')      # Ví dụ: W1234567 / 例如：W1234567
        self._numeric_pattern = re.compile(r'\d{5,12}')          # Fallback: chuỗi số thuần / 後備方案：純數字字串

    def preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        """
        Phóng to 2x và chuyển grayscale để tăng độ rõ nét cho Tesseract.
        OCR hoạt động tốt hơn trên ảnh đơn kênh có độ phân giải cao.
        放大 2 倍並轉換為灰階影像以提升 Tesseract 的辨識清晰度。
        OCR 在高解析度的單通道影像上表現更佳。
        """
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def detect_card_region(
        self, frame: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """
        Tìm contour hình chữ nhật có tỉ lệ cạnh phù hợp thẻ nhân viên (1.5–2.5).
        Nếu tìm thấy, thực hiện perspective transform để căn chỉnh thẻ về góc nhìn thẳng.
        尋找符合員工證寬高比（1.5–2.5）的矩形輪廓。
        若找到，則執行透視變換將卡片校正為正視角。
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        best_contour = None
        best_area = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 2000:  # Loại bỏ nhiễu nhỏ / 過濾掉細小雜訊
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:  # Chỉ xét hình tứ giác / 僅考慮四邊形輪廓
                x, y, w, h = cv2.boundingRect(approx)
                aspect = w / h if h > 0 else 0
                # Tỉ lệ 1.5–2.5 bao phủ thẻ ngang và thẻ ISO / 寬高比 1.5–2.5 涵蓋橫式卡片與 ISO 標準卡片
                if 1.5 <= aspect <= 2.5 and area > best_area:
                    best_area = area
                    best_contour = approx
        if best_contour is not None:
            pts = best_contour.reshape(4, 2).astype(np.float32)
            rect = self._order_points(pts)
            warped = self._perspective_transform(frame, rect)
            return frame, warped
        return frame, None

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        Sắp xếp 4 điểm góc thẻ theo thứ tự: trên-trái, trên-phải, dưới-phải, dưới-trái.
        Thứ tự chuẩn này cần thiết để perspective transform cho ra kết quả đúng hướng.
        將卡片的 4 個角點排列為：左上、右上、右下、左下的順序。
        此標準順序是透視變換產生正確方向結果的必要條件。
        """
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # Trên-trái: tổng nhỏ nhất / 左上：座標和最小
        rect[2] = pts[np.argmax(s)]   # Dưới-phải: tổng lớn nhất / 右下：座標和最大
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # Trên-phải: hiệu nhỏ nhất / 右上：座標差最小
        rect[3] = pts[np.argmax(diff)]  # Dưới-trái: hiệu lớn nhất / 左下：座標差最大
        return rect

    def _perspective_transform(
        self, frame: np.ndarray, rect: np.ndarray
    ) -> np.ndarray:
        """
        Áp dụng homography để "làm phẳng" thẻ nghiêng về ảnh top-down chuẩn.
        Giúp OCR nhận dạng chính xác hơn khi thẻ không được đặt thẳng trước camera.
        套用單應矩陣將傾斜的卡片「展平」為標準俯視圖。
        當卡片未正對攝影機時，此步驟能顯著提升 OCR 辨識準確度。
        """
        tl, tr, br, bl = rect
        w = int(max(
            np.linalg.norm(br - bl),
            np.linalg.norm(tr - tl)
        ))
        h = int(max(
            np.linalg.norm(tr - br),
            np.linalg.norm(tl - bl)
        ))
        dst = np.array([
            [0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]
        ], dtype=np.float32)
        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(frame, M, (w, h))

    def extract_id(
        self, processed_img: np.ndarray
    ) -> tuple[str, str | None]:
        """
        Chạy Tesseract và lọc kết quả qua nhiều regex theo độ ưu tiên để tìm ID dài nhất khớp.
        Dùng nhiều pattern vì ID thẻ nhân viên không đồng nhất về định dạng trên thực tế.
        執行 Tesseract 並按優先順序透過多個正則表達式篩選，取得最長匹配的 ID。
        使用多個模式是因為實務上員工證 ID 格式並不統一。
        """
        data = pytesseract.image_to_data(
            processed_img,
            config=self._ocr_config,
            output_type=pytesseract.Output.DICT
        )
        # Lọc token có độ tin cậy đủ cao — loại bỏ ký tự nhận dạng kém / 過濾信心分數足夠高的字元，去除辨識品質差的字元
        tokens = [
            data["text"][i]
            for i in range(len(data["text"]))
            if int(data["conf"][i]) > OCR_CONFIDENCE_THRESHOLD
            and data["text"][i].strip()
        ]
        raw_text = " ".join(tokens)
        best = None
        for pattern in [self._id_pattern, self._w_pattern, self._numeric_pattern]:
            for match in pattern.finditer(raw_text):
                # Cắt tiền tố không phải W hoặc số — xử lý nhiễu OCR ở đầu chuỗi / 去除非 W 或數字的前綴，處理字串開頭的 OCR 雜訊
                candidate = re.sub(r'^[^W\d]*', '', match.group())
                if candidate and (best is None or len(candidate) > len(best)):
                    best = candidate  # Ưu tiên ứng viên dài nhất để giảm false positive / 優先取最長候選以減少誤判
        return raw_text, best

    def scan_card(
        self, frame: np.ndarray, zone: tuple[int, int, int, int] | None = None
    ) -> tuple[np.ndarray, str | None]:
        """
        Pipeline đầy đủ: cắt vùng thẻ → tiền xử lý → OCR → trả về ID.
        Nếu truyền zone thì dùng trực tiếp; không thì tự phát hiện thẻ trong frame.
        完整流程：裁切卡片區域 → 預處理 → OCR → 回傳 ID。
        若提供 zone 則直接使用；否則自動在畫面中偵測卡片位置。
        """
        if zone is not None:
            x1, y1, x2, y2 = zone
            region = frame[y1:y2, x1:x2]
        else:
            frame, card_region = self.detect_card_region(frame)
            if card_region is not None:
                region = card_region
            else:
                # Fallback: dùng nửa dưới frame nếu không tìm thấy thẻ / 後備方案：若未找到卡片則使用畫面下半部
                h, w = frame.shape[:2]
                region = frame[int(h * 0.5):h, int(w * 0.15):int(w * 0.85)]
        processed = self.preprocess_for_ocr(region)
        _, employee_id = self.extract_id(processed)
        return frame, employee_id
