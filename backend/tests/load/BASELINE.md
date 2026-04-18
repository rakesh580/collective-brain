# Load Test Baseline & Performance Targets

## Target Metrics (50-100 concurrent users)

| Metric         | Target     | Critical | Notes                              |
|----------------|------------|----------|------------------------------------|
| p50 (median)   | < 200ms    | < 500ms  | Typical read endpoints             |
| p95            | < 1,000ms  | < 2,000ms| Includes slower analytics queries  |
| p99            | < 2,000ms  | < 5,000ms| Occasional slow DB queries         |
| Error rate     | < 1%       | < 5%     | Excludes expected 429 rate limits  |
| Throughput     | > 50 req/s | > 20 req/s| At 50 concurrent users            |

### Per-Endpoint Expectations

| Endpoint                          | Expected p95 | Notes                         |
|-----------------------------------|-------------|-------------------------------|
| `GET /insights/dashboard`         | < 500ms     | Most common user action       |
| `POST /query`                     | < 10,000ms  | LLM call; rate-limited 10/min |
| `GET /decisions`                  | < 300ms     | DB read                       |
| `GET /search?q=...`              | < 500ms     | Vector search                 |
| `GET /members`                    | < 200ms     | Simple DB read                |
| `GET /rooms`                      | < 200ms     | Simple DB read                |
| `GET /analytics/*`               | < 1,000ms   | Aggregation queries           |
| `GET /artifacts`                  | < 300ms     | DB read                       |
| `POST /risk-radar/scan`          | < 5,000ms   | AI-powered analysis           |
| `GET /continuity/dashboard`      | < 1,000ms   | Aggregation query             |
| `GET /graph/*`                   | < 1,000ms   | Graph traversal               |

## How to Run

### Prerequisites

```bash
pip install locust
```

### Quick Run (defaults: localhost:8000, 50 users, 60s)

```bash
cd backend
bash tests/load/run_load_test.sh
```

### Custom Run

```bash
# 100 users, 2 minutes, against staging
bash tests/load/run_load_test.sh https://staging.example.com 100 120 10
```

### Interactive Mode (Web UI)

```bash
locust -f tests/load/locustfile.py --host http://localhost:8000
# Open http://localhost:8089 in your browser
```

## How to Interpret Results

### CSV Output Files

Each run creates timestamped files in `tests/load/results/`:

- `*_stats.csv` -- Per-endpoint summary (requests, failures, response times)
- `*_stats_history.csv` -- Time-series data (requests/sec over time)
- `*_failures.csv` -- Details of every failed request
- `*_report.html` -- Visual HTML report with charts

### Key Things to Check

1. **Error rate** -- Should be < 1%. Any 5xx errors indicate server bugs.
2. **p95 response time** -- Should be < 1s for read endpoints. The AI query endpoint (`POST /query`) is expected to be slower (up to 10s).
3. **Throughput trend** -- Should be stable over time. A declining trend indicates resource exhaustion (connection pool, memory, CPU).
4. **429 responses** -- Expected on the `/query` endpoint due to rate limiting (10 req/min/user). These are excluded from failure counts in the locustfile.

### Red Flags

- p95 > 5s on any read endpoint
- Error rate > 5%
- Throughput drops by > 50% over the test duration
- Connection refused errors (server ran out of workers)
- Increasing response times over time (memory leak or connection pool exhaustion)

## When to Run

- **Before every release** -- Compare against this baseline
- **After major changes** -- Database migrations, new indexes, service refactors
- **After infrastructure changes** -- Server scaling, database upgrades, Redis config
- **Weekly (CI)** -- Optional scheduled run against staging

## Rate Limiting Considerations

The AI query endpoint (`POST /api/v1/query`) is rate-limited to 10 requests per minute per user. The locustfile accounts for this by:

1. Giving `ai_query` a low task weight (3) relative to dashboard browsing (10)
2. Marking 429 responses as "success" so they don't inflate the error rate
3. Using `wait_time = between(1, 3)` to space out requests naturally

If testing at > 50 users, expect a higher proportion of 429s on the query endpoint. This is correct behavior -- it means rate limiting is working.
