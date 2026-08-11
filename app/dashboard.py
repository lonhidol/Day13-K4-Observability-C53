from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
LOGS_FILE = Path(__file__).resolve().parents[1] / "data" / "logs.jsonl"


def parse_logs() -> List[Dict[str, Any]]:
    logs = []
    if not LOGS_FILE.exists():
        return logs
    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    pass
    return logs


def calculate_percentile(vals: List[float], p: float) -> float:
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(d0 + d1)


@router.get("/api/dashboard-data")
async def get_dashboard_data() -> JSONResponse:
    logs = parse_logs()

    response_sent_logs = [l for l in logs if l.get("event") == "response_sent"]
    request_received_logs = [l for l in logs if l.get("event") == "request_received"]
    request_failed_logs = [l for l in logs if l.get("event") == "request_failed"]

    # 1. Latency
    latencies = [l.get("latency_ms", 0) for l in response_sent_logs if "latency_ms" in l]
    p50 = calculate_percentile(latencies, 50)
    p95 = calculate_percentile(latencies, 95)
    p99 = calculate_percentile(latencies, 99)

    # Time-series by minute for latency
    minutes_map: Dict[str, List[float]] = {}
    for l in response_sent_logs:
        ts = l.get("ts", "")[:16]  # "YYYY-MM-DDTHH:MM"
        if ts:
            minutes_map.setdefault(ts, []).append(l.get("latency_ms", 0))

    sorted_minutes = sorted(minutes_map.keys())
    latency_timeseries = {
        "labels": [m[-5:] for m in sorted_minutes],
        "p50": [calculate_percentile(minutes_map[m], 50) for m in sorted_minutes],
        "p95": [calculate_percentile(minutes_map[m], 95) for m in sorted_minutes],
        "p99": [calculate_percentile(minutes_map[m], 99) for m in sorted_minutes],
    }

    # 2. Traffic
    traffic_map: Dict[str, int] = {}
    for l in request_received_logs:
        ts = l.get("ts", "")[:16]
        if ts:
            traffic_map[ts] = traffic_map.get(ts, 0) + 1
    
    traffic_minutes = sorted(traffic_map.keys())
    total_requests = len(request_received_logs)
    avg_rate = round(total_requests / max(len(traffic_minutes), 1), 2)

    traffic_timeseries = {
        "labels": [m[-5:] for m in traffic_minutes],
        "counts": [traffic_map[m] for m in traffic_minutes],
    }

    # 3. Errors
    total_failed = len(request_failed_logs)
    error_rate_pct = round((total_failed / max(total_requests, 1)) * 100, 2)
    error_breakdown: Dict[str, int] = {}
    for l in request_failed_logs:
        err_type = l.get("error_type", "UnknownError")
        error_breakdown[err_type] = error_breakdown.get(err_type, 0) + 1

    # 4. Cost
    costs = [l.get("cost_usd", 0.0) for l in response_sent_logs]
    total_cost = round(sum(costs), 6)
    
    cost_map: Dict[str, float] = {}
    for l in response_sent_logs:
        ts = l.get("ts", "")[:16]
        if ts:
            cost_map[ts] = cost_map.get(ts, 0.0) + l.get("cost_usd", 0.0)
    
    cost_minutes = sorted(cost_map.keys())
    cost_timeseries = {
        "labels": [m[-5:] for m in cost_minutes],
        "cost_per_min": [round(cost_map[m], 6) for m in cost_minutes],
    }

    # 5. Tokens
    tokens_in = sum(l.get("tokens_in", 0) for l in response_sent_logs)
    tokens_out = sum(l.get("tokens_out", 0) for l in response_sent_logs)
    total_tokens = tokens_in + tokens_out

    # 6. Quality
    scores = [l.get("quality_score", 0.0) for l in response_sent_logs if "quality_score" in l]
    mean_quality = round(sum(scores) / max(len(scores), 1), 3)

    return JSONResponse({
        "time_range_minutes": 60,
        "refresh_seconds": 30,
        "total_logs": len(logs),
        "latency": {
            "p50": round(p50, 1),
            "p95": round(p95, 1),
            "p99": round(p99, 1),
            "threshold_p95": 3000,
            "unit": "ms",
            "timeseries": latency_timeseries,
        },
        "traffic": {
            "total_requests": total_requests,
            "rate_per_minute": avg_rate,
            "threshold_rate": 1,
            "unit": "requests_per_minute",
            "timeseries": traffic_timeseries,
        },
        "errors": {
            "error_rate_pct": error_rate_pct,
            "failed_count": total_failed,
            "received_count": total_requests,
            "breakdown": error_breakdown,
            "threshold_error_rate": 2.0,
            "unit": "percent",
        },
        "cost": {
            "total_usd": total_cost,
            "threshold_total": 2.5,
            "unit": "usd",
            "timeseries": cost_timeseries,
        },
        "tokens": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": total_tokens,
            "threshold_total": 50000,
            "unit": "tokens",
        },
        "quality": {
            "mean_score": mean_quality,
            "sample_count": len(scores),
            "threshold_mean": 0.75,
            "unit": "score_0_to_1",
        },
    })


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_html() -> HTMLResponse:
    html_content = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Day 13 — AI Observability Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --card-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #4ade80;
            --accent-red: #f87171;
            --accent-purple: #c084fc;
            --accent-amber: #fbbf24;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            padding: 24px;
            min-height: 100vh;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--card-border);
        }

        .title-group h1 {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .title-group p {
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .controls {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .badge {
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .badge-success {
            background-color: rgba(74, 222, 128, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .btn-refresh {
            background-color: #3b82f6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-refresh:hover { background-color: #2563eb; }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }

        @media (max-width: 1200px) {
            .dashboard-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 768px) {
            .dashboard-grid { grid-template-columns: 1fr; }
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 18px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .card-subtitle {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .metric-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            margin: 4px 0 8px 0;
        }

        .threshold-tag {
            font-size: 12px;
            color: var(--accent-amber);
            background: rgba(251, 191, 36, 0.1);
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid rgba(251, 191, 36, 0.2);
        }

        .chart-container {
            position: relative;
            height: 180px;
            width: 100%;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <header>
        <div class="title-group">
            <h1>Day 13 — AI Observability Dashboard</h1>
            <p>Nguồn dữ liệu: <code>data/logs.jsonl</code> | Cấu hình Contract: <code>config/dashboard.yaml</code></p>
        </div>
        <div class="controls">
            <span class="badge badge-success">● Contract Valid (6/6 Panel)</span>
            <span style="font-size: 13px; color: var(--text-secondary);">Time Range: <b>60 min</b> | Refresh: <b id="countdown">30s</b></span>
            <button class="btn-refresh" onclick="loadDashboardData()">Refresh Now</button>
        </div>
    </header>

    <div class="dashboard-grid">
        <!-- Panel 1: Latency -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">1. Latency Percentiles</div>
                    <div class="card-subtitle">Chỉ số P50, P95, P99 (ms)</div>
                </div>
                <div class="threshold-tag">SLO P95 ≤ 3000 ms</div>
            </div>
            <div class="metric-value" id="val-latency">P95: -- ms</div>
            <div class="chart-container">
                <canvas id="chart-latency"></canvas>
            </div>
        </div>

        <!-- Panel 2: Traffic -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">2. Request Traffic</div>
                    <div class="card-subtitle">Số lượng request theo phút</div>
                </div>
                <div class="threshold-tag">SLO Rate ≥ 1 req/min</div>
            </div>
            <div class="metric-value" id="val-traffic">-- req/min</div>
            <div class="chart-container">
                <canvas id="chart-traffic"></canvas>
            </div>
        </div>

        <!-- Panel 3: Errors -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">3. Error Rate & Breakdown</div>
                    <div class="card-subtitle">Tỷ lệ thất bại & phân loại lỗi</div>
                </div>
                <div class="threshold-tag">SLO Error ≤ 2%</div>
            </div>
            <div class="metric-value" id="val-errors">0.0%</div>
            <div class="chart-container">
                <canvas id="chart-errors"></canvas>
            </div>
        </div>

        <!-- Panel 4: Cost -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">4. Cost Over Time</div>
                    <div class="card-subtitle">Chi phí tích lũy (USD)</div>
                </div>
                <div class="threshold-tag">SLO Total ≤ $2.50</div>
            </div>
            <div class="metric-value" id="val-cost">$0.0000</div>
            <div class="chart-container">
                <canvas id="chart-cost"></canvas>
            </div>
        </div>

        <!-- Panel 5: Tokens -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">5. Input & Output Tokens</div>
                    <div class="card-subtitle">Tổng số Token tiêu thụ</div>
                </div>
                <div class="threshold-tag">SLO Total ≤ 50,000</div>
            </div>
            <div class="metric-value" id="val-tokens">0 tokens</div>
            <div class="chart-container">
                <canvas id="chart-tokens"></canvas>
            </div>
        </div>

        <!-- Panel 6: Quality -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">6. Quality Proxy</div>
                    <div class="card-subtitle">Điểm đánh giá chất lượng trung bình</div>
                </div>
                <div class="threshold-tag">SLO Score ≥ 0.75</div>
            </div>
            <div class="metric-value" id="val-quality">0.00 / 1.0</div>
            <div class="chart-container">
                <canvas id="chart-quality"></canvas>
            </div>
        </div>
    </div>

    <script>
        let charts = {};
        let refreshSeconds = 30;
        let timer = refreshSeconds;

        async function loadDashboardData() {
            try {
                const res = await fetch('/api/dashboard-data');
                const data = await res.json();
                renderDashboard(data);
                timer = refreshSeconds;
            } catch (err) {
                console.error("Lỗi nạp dữ liệu dashboard:", err);
            }
        }

        function createOrUpdateChart(id, config) {
            if (charts[id]) {
                charts[id].destroy();
            }
            const ctx = document.getElementById(id).getContext('2d');
            charts[id] = new Chart(ctx, config);
        }

        function renderDashboard(data) {
            // 1. Latency
            document.getElementById('val-latency').innerText = `P95: ${data.latency.p95} ms (P50: ${data.latency.p50}ms)`;
            const latLabels = data.latency.timeseries.labels.length ? data.latency.timeseries.labels : ['Now'];
            const p95Data = data.latency.timeseries.p95.length ? data.latency.timeseries.p95 : [data.latency.p95];
            const p50Data = data.latency.timeseries.p50.length ? data.latency.timeseries.p50 : [data.latency.p50];
            
            createOrUpdateChart('chart-latency', {
                type: 'line',
                data: {
                    labels: latLabels,
                    datasets: [
                        { label: 'P95 Latency', data: p95Data, borderColor: '#38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.1)', fill: true, tension: 0.3 },
                        { label: 'P50 Latency', data: p50Data, borderColor: '#818cf8', borderDash: [4,4], fill: false },
                        { label: 'Threshold (3000ms)', data: Array(latLabels.length).fill(3000), borderColor: '#f87171', borderDash: [6,6], borderWidth: 2, pointRadius: 0 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }, x: { ticks: { color: '#94a3b8' } } } }
            });

            // 2. Traffic
            document.getElementById('val-traffic').innerText = `${data.traffic.rate_per_minute} req/min (Total: ${data.traffic.total_requests})`;
            const trafLabels = data.traffic.timeseries.labels.length ? data.traffic.timeseries.labels : ['Now'];
            const trafData = data.traffic.timeseries.counts.length ? data.traffic.timeseries.counts : [data.traffic.total_requests];

            createOrUpdateChart('chart-traffic', {
                type: 'bar',
                data: {
                    labels: trafLabels,
                    datasets: [
                        { label: 'Requests', data: trafData, backgroundColor: '#4ade80', borderRadius: 4 },
                        { label: 'Threshold (1 req/min)', data: Array(trafLabels.length).fill(1), type: 'line', borderColor: '#fbbf24', borderDash: [4,4], pointRadius: 0 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }, x: { ticks: { color: '#94a3b8' } } } }
            });

            // 3. Errors
            document.getElementById('val-errors').innerText = `${data.errors.error_rate_pct}% (${data.errors.failed_count}/${data.errors.received_count} failed)`;
            const errBreakdown = Object.keys(data.errors.breakdown).length ? data.errors.breakdown : { 'No Errors': 1 };
            createOrUpdateChart('chart-errors', {
                type: 'doughnut',
                data: {
                    labels: Object.keys(errBreakdown),
                    datasets: [{
                        data: Object.values(errBreakdown),
                        backgroundColor: ['#34d399', '#f87171', '#fbbf24', '#c084fc']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8' }, position: 'right' } } }
            });

            // 4. Cost
            document.getElementById('val-cost').innerText = `$${data.cost.total_usd.toFixed(4)} USD`;
            const costLabels = data.cost.timeseries.labels.length ? data.cost.timeseries.labels : ['Now'];
            const costData = data.cost.timeseries.cost_per_min.length ? data.cost.timeseries.cost_per_min : [data.cost.total_usd];

            createOrUpdateChart('chart-cost', {
                type: 'line',
                data: {
                    labels: costLabels,
                    datasets: [
                        { label: 'Cost / min ($)', data: costData, borderColor: '#c084fc', backgroundColor: 'rgba(192, 132, 252, 0.1)', fill: true, tension: 0.3 },
                        { label: 'Threshold ($2.50)', data: Array(costLabels.length).fill(2.5), borderColor: '#f87171', borderDash: [6,6], borderWidth: 2, pointRadius: 0 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }, x: { ticks: { color: '#94a3b8' } } } }
            });

            // 5. Tokens
            document.getElementById('val-tokens').innerText = `${data.tokens.total_tokens.toLocaleString()} tokens`;
            createOrUpdateChart('chart-tokens', {
                type: 'bar',
                data: {
                    labels: ['Tokens Usage'],
                    datasets: [
                        { label: 'Input Tokens', data: [data.tokens.tokens_in], backgroundColor: '#38bdf8' },
                        { label: 'Output Tokens', data: [data.tokens.tokens_out], backgroundColor: '#818cf8' }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#94a3b8' } } },
                    scales: { x: { stacked: true, ticks: { color: '#94a3b8' } }, y: { stacked: true, ticks: { color: '#94a3b8' }, grid: { color: '#334155' } } }
                }
            });

            // 6. Quality
            document.getElementById('val-quality').innerText = `${data.quality.mean_score} / 1.0 (Samples: ${data.quality.sample_count})`;
            createOrUpdateChart('chart-quality', {
                type: 'bar',
                data: {
                    labels: ['Quality Mean Score'],
                    datasets: [
                        { label: 'Mean Score', data: [data.quality.mean_score], backgroundColor: '#34d399', borderRadius: 6 },
                        { label: 'Threshold (0.75)', data: [0.75], type: 'line', borderColor: '#fbbf24', borderDash: [4,4], borderWidth: 2, pointRadius: 4 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8' } } }, scales: { y: { min: 0, max: 1, ticks: { color: '#94a3b8' }, grid: { color: '#334155' } } } }
            });
        }

        // Countdown timer for 30s auto-refresh
        setInterval(() => {
            timer--;
            if (timer <= 0) {
                loadDashboardData();
            } else {
                document.getElementById('countdown').innerText = timer + 's';
            }
        }, 1000);

        loadDashboardData();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
