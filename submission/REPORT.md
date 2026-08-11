# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: C5-3
- Repository URL: https://github.com/lonhidol/Day13-K4-Observability-C53 
- Commit SHA cuối: 5ba64725aaf0b5b4d51c28772973373d98d0f149
- Thành viên và vai trò:
  - [Tên thành viên 1] - Người 1 (Backend Observability: Logging & PII, Tracing & Prompt Version)
  - [Tên thành viên 2] - Người 2 (Monitoring & Alerting: Dashboard, SLO & Alert)
  - Đào Tùng Dương - Người 3 (Incident Lead, Report & Demo)

## 2. Kết quả kỹ thuật


- Điểm `validate_logs.py`: Baseline: 30/100, Checkpoint 1: 100/100
- Tổng số traces:
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID: req-02c0838a (Chi tiết tại file bằng chứng [log_correlation_id.json](evidence/log_correlation_id.json))
- Evidence PII redaction: Email, số điện thoại và số thẻ được che thành công (Chi tiết tại file bằng chứng [log_pii_redacted.json](evidence/log_pii_redacted.json))
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |
