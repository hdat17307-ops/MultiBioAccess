"""
Script khởi tạo một lần: tiền xử lý ảnh nhân viên thành face encodings và lưu vào file pickle.
Làm vậy để tránh tính toán lại mỗi lần khởi động — runtime chỉ cần tải file pickle là dùng được ngay.
一次性初始化腳本：將員工照片預先計算為臉部特徵向量並存入 pickle 檔案。
如此可避免每次啟動重新運算，執行期只需載入 pickle 即可直接使用。
"""

import os
import json
import pickle
import face_recognition
from config import _BASE, EMPLOYEE_DB_PATH, FACE_ENCODINGS_PATH

def build_encodings() -> None:
    """
    Đọc danh sách nhân viên từ JSON, tính face encoding cho từng ảnh và lưu kết quả.
    Dùng number_of_times_to_upsample=2 để tăng độ chính xác phát hiện khuôn mặt nhỏ hoặc xa.
    從 JSON 讀取員工清單，對每張照片計算臉部特徵向量並儲存結果。
    使用 number_of_times_to_upsample=2 以提高對小臉或遠距照片的偵測準確度。
    """
    with open(EMPLOYEE_DB_PATH) as f:
        db = json.load(f)

    results: list[dict] = []
    for emp in db["employees"]:
        img_path = os.path.join(_BASE, emp["face_image"])
        if not os.path.exists(img_path):
            print(f"SKIP (not found): {img_path}")
            continue
        img = face_recognition.load_image_file(img_path)
        # Upsample 2 lần để phát hiện khuôn mặt nhỏ trong ảnh thẻ / 對圖片進行 2 次上採樣以偵測較小的臉部
        locations = face_recognition.face_locations(img, number_of_times_to_upsample=2)
        encodings = face_recognition.face_encodings(img, locations)
        if not encodings:
            print(f"SKIP (no face detected): {img_path}")
            continue
        # Chỉ lưu encoding đầu tiên — mỗi nhân viên chỉ có một ảnh đại diện / 每位員工僅保留第一個特徵向量，因為每人只有一張大頭照
        results.append({"encoding": encodings[0], "employee": emp})
        print(f"OK: {emp['name']}")

    os.makedirs(os.path.dirname(FACE_ENCODINGS_PATH), exist_ok=True)
    with open(FACE_ENCODINGS_PATH, "wb") as f:
        pickle.dump(results, f)
    print(f"Saved {len(results)} encodings to {FACE_ENCODINGS_PATH}")

if __name__ == "__main__":
    build_encodings()
