from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "vaultis_http_requests_total",
    "HTTP requests handled, by method, URL route template, and status code.",
    ["method", "route", "status"],
)

HTTP_LATENCY = Histogram(
    "vaultis_http_request_duration_seconds",
    "Time spent handling an HTTP request.",
    ["method", "route"],
)

TRANSFERS = Counter(
    "vaultis_transfers_total",
    "Transfer attempts, by outcome (completed, or the reason it was rejected).",
    ["outcome"],
)
