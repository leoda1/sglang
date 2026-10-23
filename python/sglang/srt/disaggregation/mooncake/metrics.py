"""Prometheus observations of Python batch_transfer_sync calls."""

from functools import lru_cache


class BatchTransferMetrics:
    def __init__(self, labels, registry=None):
        # Import only after SGLang has configured PROMETHEUS_MULTIPROC_DIR.
        from prometheus_client import REGISTRY, Counter, Histogram

        registry = REGISTRY if registry is None else registry
        names = [*labels, "path"]
        self.label_values = tuple(labels.values())
        self.calls = Counter(
            "sglang:transfer_batch_calls_total",
            "Returned synchronous transfer calls, including exceptions.",
            [*names, "outcome"],
            registry=registry,
        )
        specs = (
            (
                "slices",
                "Address-list entries per returned call, including failures.",
                (1, 4, 16, 64, 256, 1024, 4096, 16384),
            ),
            (
                "bytes",
                "Requested payload bytes per returned call, including failures.",
                (
                    1024,
                    4096,
                    16384,
                    65536,
                    262144,
                    1048576,
                    4194304,
                    16777216,
                    67108864,
                ),
            ),
            (
                "duration_seconds",
                "Successful synchronous call duration, excluding preparation and metrics.",
                (0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 1),
            ),
            (
                "bandwidth_bytes_per_second",
                "Successful batch bytes divided by call duration; not NIC aggregate throughput.",
                (1e6, 1e7, 1e8, 1e9, 5e9, 1e10, 2.5e10, 5e10, 1e11, 2e11),
            ),
        )
        self.histograms = tuple(
            Histogram(
                f"sglang:transfer_batch_{name}",
                description,
                names,
                buckets=buckets,
                registry=registry,
            )
            for name, description, buckets in specs
        )

    @lru_cache(maxsize=None)
    def _path_metrics(self, path):
        values = (*self.label_values, path)
        return (
            self.calls.labels(*values, "ok"),
            self.calls.labels(*values, "failed"),
            *(metric.labels(*values) for metric in self.histograms),
        )

    def observe(self, path, slices, byte_count, elapsed_ns, success):
        ok, failed, sizes, byte_sizes, durations, bandwidths = self._path_metrics(path)
        (ok if success else failed).inc()
        sizes.observe(slices)
        byte_sizes.observe(byte_count)
        if success and elapsed_ns > 0:
            durations.observe(elapsed_ns / 1e9)
            bandwidths.observe(byte_count * 1e9 / elapsed_ns)
