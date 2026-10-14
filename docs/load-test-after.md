Target: https://d2b668bdid50ni.cloudfront.net/api
Warming up (wakes the database and Lambdas)...
Running 20 concurrent users x 15 requests each...

300 requests in 25.7s = 11.7 requests/second

| Endpoint | Requests | Success | Median | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| GET /dashboard | 75 | 92.0% | 1006 ms | 14225 ms | 15260 ms | 16244 ms |
| GET /projects | 75 | 100.0% | 33 ms | 6168 ms | 9187 ms | 13293 ms |
| GET /milestones | 75 | 100.0% | 64 ms | 1031 ms | 4771 ms | 4830 ms |
| GET /actions/summary | 75 | 98.7% | 35 ms | 6183 ms | 14596 ms | 14924 ms |
| **All** | 300 | 97.7% | 63 ms | 8197 ms | 14924 ms | 16244 ms |

Non-200 responses: {503: 7}
