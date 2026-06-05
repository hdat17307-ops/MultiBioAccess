import cv2
import numpy as np
import pytesseract
import re
from config import OCR_CONFIDENCE_THRESHOLD

class EmployeeCardScanner:
    def __init__(self):
        self._ocr_config = "--psm 11 -l eng"
        self._id_pattern = re.compile(r'[A-Z]{2,3}-?\d{4,6}')
        self._w_pattern = re.compile(r'[A-Za-z]?\d{7,11}')
        self._numeric_pattern = re.compile(r'\d{5,11}')

    def preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def detect_card_region(
        self, frame: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray | None]:
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
            if area < 2000:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect = w / h if h > 0 else 0
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
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def _perspective_transform(
        self, frame: np.ndarray, rect: np.ndarray
    ) -> np.ndarray:
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
        data = pytesseract.image_to_data(
            processed_img,
            config=self._ocr_config,
            output_type=pytesseract.Output.DICT
        )
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
                candidate = re.sub(r'^[^W\d]*', '', match.group())
                if candidate and (best is None or len(candidate) > len(best)):
                    best = candidate
        return raw_text, best

    def scan_card(
        self, frame: np.ndarray
    ) -> tuple[np.ndarray, str | None]:
        frame, card_region = self.detect_card_region(frame)
        if card_region is not None:
            region = card_region
        else:
            h, w = frame.shape[:2]
            region = frame[int(h * 0.5):h, int(w * 0.15):int(w * 0.85)]
        processed = self.preprocess_for_ocr(region)
        _, employee_id = self.extract_id(processed)
        return frame, employee_id
