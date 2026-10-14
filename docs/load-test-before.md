Before the fix (20 users x 15 requests, Lambda 128 MB, blocking action sync):

300 requests in 40.2s = 7.5 requests/second

| Endpoint | Requests | Success | Median | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| GET /dashboard | 75 | 94.7% | 786 ms | 20585 ms | 22795 ms | 26522 ms |
| GET /projects | 75 | 100.0% | 31 ms | 1013 ms | 1434 ms | 2294 ms |
| GET /milestones | 75 | 96.0% | 33 ms | 1413 ms | 10136 ms | 12505 ms |
| GET /actions/summary | 75 | 93.3% | 1563 ms | 14236 ms | 20757 ms | 23760 ms |
| **All** | 300 | 96.0% | 270 ms | 14193 ms | 22321 ms | 26522 ms |

Non-200 responses: {503: 12}
