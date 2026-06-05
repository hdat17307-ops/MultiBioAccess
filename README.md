# 多重生物辨識與門禁文字掃描系統
# Hệ Thống Kiểm Soát An Ninh Đa Sinh Trắc Học

---

> 🇹🇼 **繁體中文** 版說明請見 [第二部分](#繁體中文說明)
> 🇻🇳 **Tiếng Việt** xem [Phần đầu](#hướng-dẫn-tiếng-việt)

---

# Hướng Dẫn Tiếng Việt

## Tổng Quan

Hệ thống kết hợp nhận diện khuôn mặt, phát hiện liveness và OCR thẻ nhân viên để kiểm soát cổng ra vào.

**Luồng xác thực:**
```
Phát hiện khuôn mặt → So khớp DB → Kiểm tra liveness → Quét thẻ → Cấp/Từ chối quyền
```

---

## Yêu Cầu Hệ Thống

| Thành phần | Tối thiểu |
|---|---|
| Python | 3.11+ |
| RAM | 4 GB |
| Webcam | USB hoặc tích hợp |
| OS | Windows 10/11, macOS 11+, Ubuntu 20.04+ / Fedora 38+ |

---

## Cài Đặt Thủ Công

### Linux — Ubuntu / Debian

```bash
# 1. Cài package hệ thống
sudo apt update
sudo apt install -y \
    python3 python3-pip python3-venv \
    build-essential cmake \
    libopenblas-dev liblapack-dev \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1 \
    tesseract-ocr tesseract-ocr-eng \
    fonts-noto-cjk

# 2. Tạo môi trường ảo
cd multi_biometric_access
python3 -m venv .venv
source .venv/bin/activate

# 3. Cài dlib trước (cần compile, mất ~5 phút)
pip install cmake dlib==19.24.6

# 4. Cài các thư viện còn lại
pip install -r requirements.txt

# 5. Khởi tạo dữ liệu khuôn mặt
python setup_db.py
```

---

### Linux — Fedora / RHEL

```bash
# 1. Cài package hệ thống
sudo dnf install -y \
    python3 python3-pip \
    gcc gcc-c++ cmake \
    openblas-devel lapack-devel \
    mesa-libGL glib2 \
    tesseract tesseract-langpack-eng \
    google-noto-sans-cjk-vf-fonts

# 2. Tạo môi trường ảo
cd multi_biometric_access
python3 -m venv .venv
source .venv/bin/activate

# 3. Cài dlib trước
pip install cmake dlib==19.24.6

# 4. Cài các thư viện còn lại
pip install -r requirements.txt

# 5. Khởi tạo dữ liệu khuôn mặt
python setup_db.py
```

---

### macOS — Intel (x86_64)

```bash
# 1. Cài Homebrew (nếu chưa có)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Cài dependencies
brew install python@3.11 cmake tesseract

# 3. Cài font CJK
brew install --cask font-noto-sans-cjk

# 4. Tạo môi trường ảo
cd multi_biometric_access
python3.11 -m venv .venv
source .venv/bin/activate

# 5. Cài dlib trước
pip install cmake dlib==19.24.6

# 6. Cài các thư viện còn lại
pip install -r requirements.txt

# 7. Khởi tạo dữ liệu khuôn mặt
python setup_db.py
```

---

### macOS — Apple Silicon (M1 / M2 / M3 / M4)

> ⚠️ Chip M yêu cầu Rosetta 2 cho một số package. Làm theo đúng thứ tự dưới đây.

```bash
# 1. Cài Rosetta 2 (nếu chưa có)
softwareupdate --install-rosetta --agree-to-license

# 2. Cài Homebrew (native ARM)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 3. Cài dependencies
brew install python@3.11 cmake tesseract
brew install --cask font-noto-sans-cjk

# 4. Tạo môi trường ảo
cd multi_biometric_access
python3.11 -m venv .venv
source .venv/bin/activate

# 5. Cài dlib (native ARM — không dùng Rosetta)
pip install cmake
pip install dlib==19.24.6

# 6. Cài các thư viện còn lại
pip install -r requirements.txt

# 7. Khởi tạo dữ liệu khuôn mặt
python setup_db.py
```

> **Nếu dlib báo lỗi build trên chip M:** thử `pip install dlib --no-cache-dir`

---

### Windows 10 / 11

> ⚠️ Windows cần **Visual Studio Build Tools** để compile dlib.

**Bước 1 — Cài Python 3.11**

Tải từ [python.org/downloads](https://www.python.org/downloads/) → chọn Python 3.11.x → **tích "Add Python to PATH"** khi cài.

**Bước 2 — Cài CMake**

Tải từ [cmake.org/download](https://cmake.org/download/) → chọn bản `.msi` → **tích "Add CMake to system PATH"** khi cài.

**Bước 3 — Cài Visual Studio Build Tools**

Tải từ [visualstudio.microsoft.com/visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) → cài **"Desktop development with C++"**.

**Bước 4 — Cài Tesseract OCR**

Tải từ [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki) → cài bản `tesseract-ocr-w64-setup-*.exe` → **tích "Add to PATH"**.

**Bước 5 — Cài font CJK**

Tải [Noto Sans CJK](https://github.com/notofonts/noto-cjk/releases) → giải nén → click chuột phải vào file `.ttc` → **Install for all users**.

**Bước 6 — Cài Python packages**

Mở **Command Prompt** hoặc **PowerShell** với quyền Administrator:

```bat
cd multi_biometric_access
python -m venv .venv
.venv\Scripts\activate

pip install cmake dlib==19.24.6
pip install -r requirements.txt
```

> **Nếu dlib vẫn lỗi trên Windows:** Tải pre-built wheel từ [github.com/z-mahmud22/Dlib_Windows_Python3.x](https://github.com/z-mahmud22/Dlib_Windows_Python3.x) rồi `pip install dlib-*.whl`

**Bước 7 — Khởi tạo dữ liệu**

```bat
python setup_db.py
```

---

## Chạy Hệ Thống

```bash
# Kích hoạt môi trường ảo (nếu chưa)
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows

# Vào thư mục app
cd multi_biometric_access

# Chạy
python main.py
```

Nhấn **Q** để thoát.

---

## Thêm Nhân Viên Mới

1. Đặt ảnh khuôn mặt (JPEG, rõ mặt, ánh sáng tốt) vào `data/faces/empXXX.jpeg`
2. Mở `data/employees.json` và thêm entry:

```json
{
  "id": "EMP-003",
  "name": "Tên Nhân Viên",
  "department": "Phòng Ban",
  "face_image": "data/faces/emp003.jpeg",
  "card_id": "MÃ_THẺ"
}
```

3. Rebuild dữ liệu:

```bash
python setup_db.py
```

---

## Xử Lý Sự Cố

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `No module named 'cv2'` | Chưa cài opencv | `pip install opencv-python` |
| `No module named 'dlib'` | Dlib chưa compile | Kiểm tra cmake + build tools |
| `TesseractNotFoundError` | Tesseract chưa trong PATH | Thêm Tesseract vào PATH hệ thống |
| Camera không mở | Index camera sai | Sửa `CAMERA_INDEX` trong `config.py` (thử 0, 1, 2) |
| Font hiện ô vuông | Font CJK chưa cài | Cài `fonts-noto-cjk` (Linux) hoặc Noto Sans CJK |
| `face_encodings.pkl not found` | Chưa chạy setup | Chạy `python setup_db.py` |

---
---

# 繁體中文說明

## 系統概覽

本系統結合人臉辨識、活體偵測與員工證 OCR 掃描，實現門禁存取控制。

**驗證流程：**
```
偵測人臉 → 比對資料庫 → 活體檢測 → 掃描員工證 → 授權/拒絕
```

---

## 系統需求

| 項目 | 最低需求 |
|---|---|
| Python | 3.11+ |
| 記憶體 | 4 GB |
| 攝影機 | USB 或內建 |
| 作業系統 | Windows 10/11、macOS 11+、Ubuntu 20.04+ / Fedora 38+ |

---

## 手動安裝教學

### Linux — Ubuntu / Debian

```bash
# 1. 安裝系統套件
sudo apt update
sudo apt install -y \
    python3 python3-pip python3-venv \
    build-essential cmake \
    libopenblas-dev liblapack-dev \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1 \
    tesseract-ocr tesseract-ocr-eng \
    fonts-noto-cjk

# 2. 建立虛擬環境
cd multi_biometric_access
python3 -m venv .venv
source .venv/bin/activate

# 3. 優先安裝 dlib（需編譯，約需 5 分鐘）
pip install cmake dlib==19.24.6

# 4. 安裝其餘套件
pip install -r requirements.txt

# 5. 初始化人臉資料
python setup_db.py
```

---

### Linux — Fedora / RHEL

```bash
# 1. 安裝系統套件
sudo dnf install -y \
    python3 python3-pip \
    gcc gcc-c++ cmake \
    openblas-devel lapack-devel \
    mesa-libGL glib2 \
    tesseract tesseract-langpack-eng \
    google-noto-sans-cjk-vf-fonts

# 2. 建立虛擬環境
cd multi_biometric_access
python3 -m venv .venv
source .venv/bin/activate

# 3. 優先安裝 dlib
pip install cmake dlib==19.24.6

# 4. 安裝其餘套件
pip install -r requirements.txt

# 5. 初始化人臉資料
python setup_db.py
```

---

### macOS — Intel（x86_64）

```bash
# 1. 安裝 Homebrew（若尚未安裝）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安裝相依套件
brew install python@3.11 cmake tesseract

# 3. 安裝 CJK 字型
brew install --cask font-noto-sans-cjk

# 4. 建立虛擬環境
cd multi_biometric_access
python3.11 -m venv .venv
source .venv/bin/activate

# 5. 優先安裝 dlib
pip install cmake dlib==19.24.6

# 6. 安裝其餘套件
pip install -r requirements.txt

# 7. 初始化人臉資料
python setup_db.py
```

---

### macOS — Apple Silicon（M1 / M2 / M3 / M4）

> ⚠️ Apple Silicon 晶片部分套件需要 Rosetta 2，請依序執行以下步驟。

```bash
# 1. 安裝 Rosetta 2（若尚未安裝）
softwareupdate --install-rosetta --agree-to-license

# 2. 安裝 Homebrew（原生 ARM 版本）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 3. 安裝相依套件
brew install python@3.11 cmake tesseract
brew install --cask font-noto-sans-cjk

# 4. 建立虛擬環境
cd multi_biometric_access
python3.11 -m venv .venv
source .venv/bin/activate

# 5. 安裝 dlib（原生 ARM，無需 Rosetta）
pip install cmake
pip install dlib==19.24.6

# 6. 安裝其餘套件
pip install -r requirements.txt

# 7. 初始化人臉資料
python setup_db.py
```

> **若 dlib 在 Apple Silicon 上編譯失敗：** 執行 `pip install dlib --no-cache-dir`

---

### Windows 10 / 11

> ⚠️ Windows 需要 **Visual Studio Build Tools** 才能編譯 dlib。

**步驟一 — 安裝 Python 3.11**

前往 [python.org/downloads](https://www.python.org/downloads/) 下載 Python 3.11.x → 安裝時**勾選「Add Python to PATH」**。

**步驟二 — 安裝 CMake**

前往 [cmake.org/download](https://cmake.org/download/) 下載 `.msi` 安裝檔 → 安裝時**勾選「Add CMake to system PATH」**。

**步驟三 — 安裝 Visual Studio Build Tools**

前往 [visualstudio.microsoft.com/visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) → 安裝 **「Desktop development with C++」** 工作負載。

**步驟四 — 安裝 Tesseract OCR**

前往 [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki) 下載 `tesseract-ocr-w64-setup-*.exe` → 安裝時**勾選「Add to PATH」**。

**步驟五 — 安裝 CJK 字型**

下載 [Noto Sans CJK](https://github.com/notofonts/noto-cjk/releases) → 解壓縮 → 對 `.ttc` 檔案按右鍵 → **「為所有使用者安裝」**。

**步驟六 — 安裝 Python 套件**

以系統管理員開啟 **命令提示字元** 或 **PowerShell**：

```bat
cd multi_biometric_access
python -m venv .venv
.venv\Scripts\activate

pip install cmake dlib==19.24.6
pip install -r requirements.txt
```

> **若 dlib 在 Windows 上仍然失敗：** 至 [github.com/z-mahmud22/Dlib_Windows_Python3.x](https://github.com/z-mahmud22/Dlib_Windows_Python3.x) 下載預編譯 wheel，再執行 `pip install dlib-*.whl`

**步驟七 — 初始化人臉資料**

```bat
python setup_db.py
```

---

## 啟動系統

```bash
# 啟用虛擬環境（若尚未啟用）
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows

# 進入應用程式目錄
cd multi_biometric_access

# 執行
python main.py
```

按 **Q** 鍵退出系統。

---

## 新增員工

1. 將員工正臉照片（JPEG 格式、清晰、光線充足）放入 `data/faces/empXXX.jpeg`
2. 編輯 `data/employees.json`，新增以下項目：

```json
{
  "id": "EMP-003",
  "name": "員工姓名",
  "department": "部門名稱",
  "face_image": "data/faces/emp003.jpeg",
  "card_id": "員工證號碼"
}
```

3. 重新建立人臉編碼資料庫：

```bash
python setup_db.py
```

---

## 常見問題排除

| 錯誤訊息 | 原因 | 解決方法 |
|---|---|---|
| `No module named 'cv2'` | 未安裝 opencv | `pip install opencv-python` |
| `No module named 'dlib'` | dlib 未編譯成功 | 確認 cmake 與 build tools 已安裝 |
| `TesseractNotFoundError` | Tesseract 不在 PATH 中 | 將 Tesseract 加入系統 PATH |
| 攝影機無法開啟 | 攝影機索引錯誤 | 修改 `config.py` 中的 `CAMERA_INDEX`（嘗試 0、1、2） |
| 文字顯示方框 | 未安裝 CJK 字型 | 安裝 `fonts-noto-cjk`（Linux）或 Noto Sans CJK |
| `face_encodings.pkl not found` | 尚未執行初始化 | 執行 `python setup_db.py` |

---

## Python 套件版本參考

| 套件 | 版本 |
|---|---|
| opencv-python | 4.13.0 |
| mediapipe | 0.10.30 |
| face-recognition | 1.3.0 |
| dlib | 19.24.6 |
| pytesseract | 0.3.13 |
| cvzone | 1.6.1 |
| Pillow | 12.2.0 |
| numpy | 2.4.4 |
