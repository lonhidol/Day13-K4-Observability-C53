# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: C5-3
- Repository URL: https://github.com/lonhidol/Day13-K4-Observability-C53 
- Commit SHA cuối: 5ba64725aaf0b5b4d51c28772973373d98d0f149
- Thành viên và vai trò:
  - Nguyễn Thành Long - 2A202601536 - Người 1 (Backend Observability: Logging & PII, Tracing & Prompt Version)
  - Hoàng Xuân Quân - 2A202601868 - Người 2 (Monitoring & Alerting: Dashboard, SLO & Alert)
  - Đào Tùng Dương - 2A202601402 - Người 3 (Incident Lead, Report & Demo)

## 2. Kết quả kỹ thuật


- Điểm `validate_logs.py`: Baseline: 30/100, Checkpoint 1: 100/100
- Tổng số traces: > 20 traces
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: http://localhost:8000/dashboard 

## 3. Logging và tracing

- Evidence correlation ID: req-02c0838a (Chi tiết tại file bằng chứng [log_correlation_id.json](evidence/log_correlation_id.json))
- Evidence PII redaction: Email, số điện thoại và số thẻ được che thành công (Chi tiết tại file bằng chứng [log_pii_redacted.json](evidence/log_pii_redacted.json))
- Evidence trace waterfall: [trace_detail.png](evidence/trace_detail.png)
- Giải thích một span đáng chú ý: Span `mock_rag` (hoặc `mock_llm`) là đáng chú ý nhất vì khi incident `rag_slow` được kích hoạt, thời gian thực thi của span này tăng đột biến (chiếm đến 90% tổng latency), từ đó định vị chính xác bộ phận bị nghẽn trong hệ thống.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: `production` (v1)
- Version/label candidate: `candidate` (v2)
- Trace ID của mỗi version: Xem chi tiết trong Langfuse Dashboard của nhóm.
- Bằng chứng đổi label hoặc rollback: [prompt_rollback.png](evidence/prompt_rollback.png)

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: HỢP LỆ: 6/6 panel (Chi tiết tại [validate_dashboard.txt](evidence/validate_dashboard.txt))
- Evidence dashboard: [evidence_baseline.png.jpg](evidence/evidence_baseline.png.jpg) (Baseline) và [evidence_incident_rag_slow.png.jpg](evidence/evidence_incident_rag_slow.png.jpg) (Incident)
- SLO đã chọn và lý do: p95 latency < 2000ms cho các request thông thường. Lý do chọn SLO này là để phát hiện sớm các hiện tượng suy giảm hiệu năng hệ thống (ví dụ khi bị nghẽn mạng hay LLM/RAG phản hồi chậm như sự cố `rag_slow` làm latency nhảy vọt lên > 3.5s).
- Alert rules và runbook:
  * Alert rules: Nếu p95 latency > 3000ms trong 3 phút liên tục hoặc tỷ lệ lỗi HTTP 5xx > 5% trong 5 phút thì kích hoạt alert.
  * Runbook: 
    1. Xác định triệu chứng lỗi từ Dashboard.
    2. Mở Langfuse tìm trace ID có latency cao để định vị span bị lỗi/chậm.
    3. Lọc logs theo `correlation_id` của trace lỗi để tìm nguyên nhân cụ thể trong code.
    4. Nếu lỗi do phiên bản prompt mới, thực hiện rollback prompt về phiên bản ổn định trước đó trên Langfuse.

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1`
- Triệu chứng từ metrics: p95 latency của API chat tăng đột biến vượt ngưỡng SLO cam kết (tăng từ mức bình thường ~1.2 giây lên tới 2.6 giây - 3.6 giây trên server và lên tới 12 - 14.7 giây phía client khi chịu tải đồng thời 5 requests), trong khi tỷ lệ lỗi vẫn là 0% (HTTP 200).
- Trace ID liên quan: Các trace ID tương ứng với các request có latency cao trong đợt challenge (ví dụ trace ID liên kết với correlation ID `req-c34d8986` trên Langfuse dashboard của nhóm).
- Log line/correlation ID liên quan: Correlation ID tiêu biểu: `req-c34d8986` (Chi tiết tại file log tải [challenge_incident_load_test.txt](evidence/challenge_incident_load_test.txt)). Dòng log API phản hồi gửi đi ghi nhận độ trễ lớn:
  `{"service": "api", "latency_ms": 2651, "tokens_in": 35, "tokens_out": 103, "cost_usd": 0.00165, "quality_score": 0.8, "payload": {"answer_preview": "Starter answer. Teams should improve this output logic and add better quality ch..."}, "event": "response_sent", "correlation_id": "req-c34d8986", "model": "claude-sonnet-4-5", "session_id": "k4-challenge-s01", "user_id_hash": "f00ba60b3772", "env": "dev", "feature": "monitoring", "level": "info", "ts": "2026-08-11T08:41:48.927179Z"}`
- Root cause: Incident `rag_slow` được kích hoạt khiến thành phần RAG retrieval bị sleep/delay giả lập (gây thắt nút cổ chai), làm chậm luồng xử lý của các request sử dụng tính năng RAG (đặc biệt là các query thuộc feature `monitoring`).
- Fix action: Gọi endpoint control `/incidents/rag_slow/disable` để tắt incident (đã khôi phục hệ thống về trạng thái bình thường). Trong thực tế: Tối ưu truy vấn database, cấu hình timeout cho kết nối Vector DB, và triển khai bộ nhớ đệm cache cho kết quả RAG.
- Preventive measure: Cấu hình Alerting gửi cảnh báo khi p95 latency của riêng span RAG vượt quá 1000ms trong 3 phút liên tục. Triển khai Circuit Breaker để tự động ngắt kết nối và fallback sang chế độ chat LLM thông thường (không qua RAG) khi RAG bị timeout, đảm bảo tính sẵn sàng của API.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Nguyễn Thành Long (Người 1) | Phát triển phần Logging, PII Redaction và tích hợp Tracing/Prompt Version trên Langfuse. | Commit: `1d4d6f3` | Hiểu cách thiết lập log JSON có cấu trúc, che PII thô và cơ chế rollback prompt trên Langfuse. |
| Hoàng Xuân Quân (Người 2) | Dựng Dashboard giám sát 6 panel, thiết lập chỉ số SLO và biên soạn Runbook xử lý sự cố. | Commits: `dd862cc`, `0810b7b` | Nắm rõ cách xây dựng, trực quan hóa số liệu và tối ưu giao diện dashboard giám sát hệ thống AI. |
| Đào Tùng Dương (Người 3) | Kích hoạt sự cố, chạy load test dữ liệu thực hành và challenge chính thức, điều tra nguyên nhân gốc rễ và tổng hợp báo cáo. | Commits: `0609462`, `ab2f58e` | Thực hành thành thạo quy trình xử lý sự cố thực tế theo luồng Metrics -> Traces -> Logs để định vị lỗi thắt nút cổ chai. |
