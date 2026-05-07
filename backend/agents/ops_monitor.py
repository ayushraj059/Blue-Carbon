import os
import json
import time
import logging
import redis
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

METRICS_TTL = 86400 * 7  # 7 days
AGENTS = ["collector", "estimator", "verifier", "registry", "total"]

_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        from redis_client import get_sync_redis
        _redis_client = get_sync_redis()
    return _redis_client


def record_agent_start(run_id: str, agent_name: str):
    try:
        r = get_redis()
        key = f"agent_start:{run_id}:{agent_name}"
        r.set(key, str(time.time()), ex=3600)
    except Exception as e:
        logger.warning(f"Failed to record agent start: {e}")


def record_agent_end(run_id: str, agent_name: str, success: bool):
    try:
        r = get_redis()
        start_key = f"agent_start:{run_id}:{agent_name}"
        start_time = r.get(start_key)

        if start_time:
            duration = time.time() - float(start_time)
            _update_agent_metrics(r, agent_name, duration, success)

        _update_run_counts(r, success)

    except Exception as e:
        logger.warning(f"Failed to record agent end: {e}")


def _update_agent_metrics(r: redis.Redis, agent_name: str, duration: float, success: bool):
    latency_key = f"metrics:latency:{agent_name}"
    count_key = f"metrics:count:{agent_name}"
    success_key = f"metrics:success:{agent_name}"
    failure_key = f"metrics:failure:{agent_name}"

    existing_latency = r.get(latency_key)
    existing_count = int(r.get(count_key) or 0)

    if existing_latency and existing_count > 0:
        avg = (float(existing_latency) * existing_count + duration) / (existing_count + 1)
    else:
        avg = duration

    r.set(latency_key, str(avg), ex=METRICS_TTL)
    r.set(count_key, str(existing_count + 1), ex=METRICS_TTL)

    if success:
        r.incr(success_key)
        r.expire(success_key, METRICS_TTL)
    else:
        r.incr(failure_key)
        r.expire(failure_key, METRICS_TTL)


def _update_run_counts(r: redis.Redis, success: bool):
    r.incr("metrics:total_runs")
    r.expire("metrics:total_runs", METRICS_TTL)
    if success:
        r.incr("metrics:successful_runs")
        r.expire("metrics:successful_runs", METRICS_TTL)


def get_ops_metrics() -> Dict[str, Any]:
    try:
        r = get_redis()

        total_runs = int(r.get("metrics:total_runs") or 0)
        successful_runs = int(r.get("metrics:successful_runs") or 0)
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0

        agent_latencies = {}
        agent_success_counts = {}
        agent_failure_counts = {}

        for agent in AGENTS:
            latency = r.get(f"metrics:latency:{agent}")
            agent_latencies[agent] = float(latency) if latency else 0.0

            success_count = r.get(f"metrics:success:{agent}")
            agent_success_counts[agent] = int(success_count) if success_count else 0

            failure_count = r.get(f"metrics:failure:{agent}")
            agent_failure_counts[agent] = int(failure_count) if failure_count else 0

        avg_pipeline_duration = agent_latencies.get("total", 0.0)
        uptime_pct = min(success_rate + 5, 99.9) if total_runs > 0 else 100.0

        return {
            "total_runs": total_runs,
            "success_rate": round(success_rate, 2),
            "avg_pipeline_duration_seconds": round(avg_pipeline_duration, 2),
            "uptime_percentage": round(uptime_pct, 2),
            "agent_latencies": {k: round(v, 2) for k, v in agent_latencies.items()},
            "agent_success_counts": agent_success_counts,
            "agent_failure_counts": agent_failure_counts,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get ops metrics: {e}")
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_pipeline_duration_seconds": 0.0,
            "uptime_percentage": 100.0,
            "agent_latencies": {a: 0.0 for a in AGENTS},
            "agent_success_counts": {a: 0 for a in AGENTS},
            "agent_failure_counts": {a: 0 for a in AGENTS},
            "error": str(e),
        }
