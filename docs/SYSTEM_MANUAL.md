# Short URL Generator - System Architecture & Technical Manual 📘

คู่มือระบบเชิงเทคนิคสำหรับนักพัฒนาระบบ ผู้ดูแลระบบ (System Admin) และผู้ดูแลรักษาโครงสร้างพื้นฐาน

---

## 1. ภาพรวมสถาปัตยกรรมระบบ (System Overview)

ระบบ Short URL Generator ได้รับการออกแบบตามแนวคิด **Clean Modular Layered Architecture** โดยแบ่งระดับชั้นความรับผิดชอบออกเป็น:

```text
[ Client Requests (Browser / API Clients) ]
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│ Presentation & Routing Layer (FastAPI)                 │
│ • main.py: Endpoints, Exception Handlers, Middleware   │
│ • auth.py: Security Guard (X-API-Key Verification)     │
│ • schemas.py: Pydantic v2 Request/Response Validation  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Business Logic & Service Layer                         │
│ • crud.py: Base62 Code Generator, Collision Detection, │
│   Expiration Logic, Click Recorder                     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Data Access & Persistence Layer                        │
│ • database.py: SQLAlchemy Engine, Session Local        │
│ • models.py: URLItem, ClickLog Database Entities       │
│ • Storage: SQLite Database Engine                      │
└────────────────────────────────────────────────────────┘
```

---

## 2. พจนานุกรมข้อมูล (Data Dictionary & Schemas)

### 2.1 ตาราง `urls` (URL Items)
จัดเก็บข้อมูลความสัมพันธ์ระหว่างรหัสย่อและลิงก์ปลายทาง

| คอลัมน์ | ชนิดข้อมูล | เงื่อนไข (Constraints) | คำอธิบาย |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PRIMARY KEY, AUTOINCREMENT | รหัสประจำแถวข้อมูล |
| `original_url` | `TEXT` | NOT NULL | URL ปลายทางจริง |
| `short_code` | `VARCHAR(10)` | UNIQUE, INDEX, NOT NULL | รหัสย่อความยาว 6 ตัวอักษร (Base62) |
| `click_count` | `INTEGER` | DEFAULT 0, NOT NULL | จำนวนครั้งที่ถูกคลิกสะสม |
| `expires_at` | `DATETIME` | NULLABLE | วันเวลาหมดอายุ (UTC) |
| `created_at` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | วันเวลาที่สร้างลิงก์ (UTC) |

### 2.2 ตาราง `click_logs` (Click Analytics)
บันทึกประวัติการเปิดลิงก์ย่อแบบละเอียด

| คอลัมน์ | ชนิดข้อมูล | เงื่อนไข (Constraints) | คำอธิบาย |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | PRIMARY KEY, AUTOINCREMENT | รหัสประจำแถวข้อมูล |
| `url_id` | `INTEGER` | FOREIGN KEY (`urls.id`), INDEX | รหัสอ้างอิงตาราง `urls` (CASCADE Delete) |
| `clicked_at` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | วันเวลาที่เกิดการคลิก (UTC) |
| `user_agent` | `TEXT` | NULLABLE | ข้อมูล Browser / Device ของผู้เปิดลิงก์ |
| `referrer` | `TEXT` | NULLABLE | แหล่งที่มาของทราฟฟิก (Referer Header) |

---

## 3. เอกสารสัญญา API ละเอียด (Comprehensive API Reference)

### 3.1 สร้างลิงก์ย่อ (`POST /api/v1/shorten`)
- **Headers:** `X-API-Key: <SECRET_KEY>`, `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "original_url": "https://example.com/target-path",
    "expires_in_hours": 24
  }
  ```
- **Response Success (201 Created):**
  ```json
  {
    "short_code": "k9Lm2P",
    "short_url": "http://localhost:8000/k9Lm2P",
    "original_url": "https://example.com/target-path",
    "expires_at": "2026-09-11T09:00:00Z",
    "created_at": "2026-09-10T09:00:00Z"
  }
  ```
- **Error Codes:**
  - `401 Unauthorized`: ขาด Header `X-API-Key`
  - `403 Forbidden`: ค่า API Key ไม่ถูกต้อง
  - `422 Unprocessable Entity`: URL ผิดรูปแบบหรือไม่ผ่าน Validation

---

### 3.2 เปิดลิงก์ย่อ (`GET /{short_code}`)
- **Public Endpoint:** ไม่ต้องใช้ API Key
- **Response Success:** `307 Temporary Redirect` พร้อม `Location: <original_url>`
- **Error Responses:**
  - `404 Not Found`: ไม่พบรหัสย่อนี้ในระบบ
  - `410 Gone`: ลิงก์ย่อนี้หมดอายุการใช้งานแล้ว

---

### 3.3 ตรวจสอบสถิติ (`GET /api/v1/analytics/{short_code}`)
- **Headers:** `X-API-Key: <SECRET_KEY>`
- **Response Success (200 OK):**
  ```json
  {
    "short_code": "k9Lm2P",
    "original_url": "https://example.com/target-path",
    "total_clicks": 5,
    "is_expired": false,
    "expires_at": "2026-09-11T09:00:00Z",
    "recent_clicks": [
      {
        "clicked_at": "2026-09-10T09:30:15Z",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        "referrer": "https://facebook.com"
      }
    ]
  }
  ```

---

## 4. มาตรฐานความปลอดภัย (Security & Authorization)

1. **API Key Guard:** ใช้ Dependency Injection ตรวจสอบค่า `X-API-Key` เทียบกับ Environment Variable ป้องกัน Brute-Force เบื้องต้น
2. **SQL Injection Prevention:** ใช้ SQLAlchemy 2.0 ORM Parameterized Queries ในทุกการเรียกดูข้อมูล ไม่มีการต่อสตริง SQL
3. **Container Hardening:** Dockerfile รันภายใต้สิทธิ์ผู้ใช้จำกัด (`USER appuser`) ไม่ใช้สิทธิ์ Root

---

## 5. การสำรองข้อมูลและการดูแลรักษาระบบ (Maintenance & Backup)

- **ไฟล์ฐานข้อมูล SQLite:** ถูกจัดเก็บไว้ใน Named Volume `short-data` (แมปไปยัง `/app/data/short_url.db` ภายในคอนเทนเนอร์)
- **คำสั่งสำรองข้อมูลด่วน:**
  ```bash
  docker compose exec short-url-api sqlite3 /app/data/short_url.db ".backup '/app/data/backup_$(date +%Y%m%d).db'"
  ```

---

## 6. การรันเซิร์ฟเวอร์ในสภาพแวดล้อม Local Development

เมื่อต้องการรันเซิร์ฟเวอร์เพื่อพัฒนาหรือทดสอบในเครื่อง ให้เปิด Terminal ที่ไดเรกทอรี `short/` แล้วใช้คำสั่ง:

```bash
# ติดตั้ง dependencies
pip install -r requirements.txt

# รันเซิร์ฟเวอร์พร้อม Hot-reload
python3 -m uvicorn src.main:app --reload --port 8000

# รัน Automated Test Suite
pytest tests/ -v
```
- Swagger UI Documentation: `http://localhost:8000/docs`
- Healthcheck Endpoint: `http://localhost:8000/health`
