# Short URL Generator API 🚀

[![CI/CD Pipeline](https://github.com/thitithup/ineco_short_url/actions/workflows/ci.yml/badge.svg)](https://github.com/thitithup/ineco_short_url/actions/workflows/ci.yml)

ระบบบริการย่อลิงก์ (URL Shortener) และวิเคราะห์สถิติการคลิก (Click Analytics) ประสิทธิภาพสูง พัฒนาโดย **Ineco Software House** ด้วย **Python FastAPI + SQLAlchemy + SQLite**

---

## ✨ ฟีเจอร์หลัก (Key Features)

- 🔗 **Shorten URL:** สุ่มรหัส Base62 6 หลัก (`[a-zA-Z0-9]`) อัตโนมัติ ป้องกันการชนกันของรหัส
- ⏳ **Expiration Management:** รองรับการกำหนดวันหมดอายุเป็นชั่วโมง (หากหมดอายุจะตอบกลับ HTTP 410 Gone)
- 🔀 **High-Speed Redirection:** ส่งต่อผู้เข้าชมด้วย HTTP 307 Temporary Redirect
- 📊 **Click Analytics:** บันทึกยอดคลิกสะสม วันเวลา อุปกรณ์ (User-Agent) และ Referrer
- 🔑 **API Key Security:** ป้องกันการสร้างและดูสถิติด้วย `X-API-Key` Header

---

## 🛠️ ความต้องการของระบบ (Prerequisites)

- **Python:** 3.11 หรือใหม่กว่า
- **Docker & Docker Compose** (ทางเลือกสำหรับการรันบน Container)

---

## 🚀 เริ่มต้นใช้งานในเครื่อง (Local Setup)

### 1. เข้าสู่โฟลเดอร์โปรเจกต์และติดตั้ง Dependencies
```bash
# ตรวจสอบว่าอยู่ที่โฟลเดอร์ short
python3 -m venv .venv
source .venv/bin/activate  # บน Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. กำหนดค่า Environment
```bash
cp .env.example .env
```

### 3. รันเซิร์ฟเวอร์
```bash
uvicorn src.main:app --reload --port 8000
```
- Interactive API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 การทดสอบระบบ (Running Tests)

รันชุดทดสอบความถูกต้องและการทำงานอัตโนมัติด้วย `pytest`:
```bash
pytest tests/ -v
```

---

## 🔄 ระบบ CI/CD อัตโนมัติ (Continuous Integration)

โปรเจกต์นี้ติดตั้งระบบ CI/CD Pipeline อัตโนมัติผ่าน **GitHub Actions** (`.github/workflows/ci.yml`) ที่จะทำงานทุกครั้งที่มีการ `push` หรือเปิด `Pull Request` เข้าสู่ `main`:
1. **Automated Unit & Integration Tests:** ทดสอบทุก Endpoint ผ่าน Python 3.12 ด้วย `pytest`
2. **Container Build Verification:** ทดสอบประกอบร่าง Docker Image จริงเพื่อรับประกันว่าพร้อมส่งมอบงานเสมอ
3. **Status Badge:** แสดงผลลัพธ์ผ่าน/ไม่ผ่านสดๆ ที่หัวข้อ README

---

## 🐳 รันผ่าน Docker & Docker Compose
```bash
docker compose up --build -d
```
ตรวจสอบสถานะคอนเทนเนอร์:
```bash
docker compose ps
```

---

## 📡 ตัวอย่างการเรียกใช้งาน API (cURL Examples)

### 1. สร้างลิงก์ย่อ (Shorten URL)
```bash
curl -X POST http://localhost:8000/api/v1/shorten \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ineco-secret-key-12345" \
  -d '{
    "original_url": "https://www.ineco-software.com/careers/backend-engineer",
    "expires_in_hours": 72
  }'
```

**ตัวอย่าง Response (201 Created):**
```json
{
  "short_code": "aB3d9Z",
  "short_url": "http://localhost:8000/aB3d9Z",
  "original_url": "https://www.ineco-software.com/careers/backend-engineer",
  "expires_at": "2026-09-13T09:00:00Z",
  "created_at": "2026-09-10T09:00:00Z"
}
```

### 2. ทดสอบเปิดลิงก์ย่อ (Redirect)
```bash
curl -i http://localhost:8000/aB3d9Z
```
*(ระบบจะตอบกลับ HTTP 307 พร้อม Header `Location: https://...`)*

### 3. ดูสถิติการคลิก (Analytics)
```bash
curl -X GET http://localhost:8000/api/v1/analytics/aB3d9Z \
  -H "X-API-Key: ineco-secret-key-12345"
```

---

## 🤖 การเชื่อมต่อใช้งานร่วมกับ AI Assistant (MCP Server)

ระบบรองรับ **Model Context Protocol (MCP)** สำหรับให้ AI Agents (Google Antigravity IDE, Claude Desktop, Cursor) เรียกใช้งานฟังก์ชันย่อลิงก์และดูสถิติได้ทันทีทั้งแบบ Local Process (`stdio`) และ Web API Endpoint (`http://localhost:8000/mcp`)

### การตั้งค่า Client

#### แบบที่ 1: Local CLI (`stdio`)
```json
{
  "mcpServers": {
    "ineco-short-url": {
      "command": "/path/to/short/.venv/bin/python3",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/short"
    }
  }
}
```

#### แบบที่ 2: Web API Route (`Streamable HTTP`)
เมื่อรัน FastAPI Web API (`uvicorn src.main:app --port 8000`) สามารถเชื่อมต่อผ่าน Remote URL:
```json
{
  "mcpServers": {
    "ineco-short-url-remote": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### เครื่องมือที่ AI สามารถเรียกใช้ได้ (MCP Tools):
- 🔗 `shorten_url(url, expires_in_hours)`: สร้างลิงก์สั้นใหม่
- 🔍 `resolve_url(short_code)`: ตรวจสอบ URL ปลายทางโดยไม่เพิ่มยอดคลิก (Safe Inspection)
- 📊 `get_url_analytics(short_code)`: ดึงข้อมูลสถิติและการคลิก
- 📋 `short://recent-urls` (Resource): อ่านรายการ 10 ลิงก์ล่าสุด

