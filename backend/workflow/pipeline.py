import json
import time
import logging
import asyncio
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from datetime import datetime, timezone
import redis as sync_redis

from langgraph.graph import StateGraph, END
from agents.collector import run_collector
from agents.estimator import run_estimator
from agents.verifier import run_verifier
from agents.registry_agent import run_registry_agent
from agents.ops_monitor import record_agent_start, record_agent_end, get_redis

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class PipelineState(TypedDict):
    run_id: str
    file_path: str
    raw_data: Optional[List[Dict[str, Any]]]
    validated_data: Optional[List[Dict[str, Any]]]
    carbon_estimates: Optional[List[Dict[str, Any]]]
    total_carbon_tons: float
    verification_result: Optional[Dict[str, Any]]
    blockchain_result: Optional[Dict[str, Any]]
    errors: List[str]
    retry_count: int
    status: str
    correction_context: str
    step_timings: Dict[str, float]


def _publish_progress(run_id: str, step: str, status: str, message: str, data: Optional[Dict] = None):
    try:
        r = get_redis()
        payload = {
            "run_id": run_id,
            "step": step,
            "status": status,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        r.publish(f"pipeline:{run_id}", json.dumps(payload))
    except Exception as e:
        logger.warning(f"Failed to publish progress: {e}")


def node_collector(state: PipelineState) -> PipelineState:
    run_id = state["run_id"]
    _publish_progress(run_id, "collector", "running", "Collecting and validating CSV data...")
    record_agent_start(run_id, "collector")
    start = time.time()

    try:
        result = run_collector(state["file_path"])
        duration = time.time() - start

        if result["status"] == "error":
            errors = state.get("errors", []) + [result.get("error", "Collection failed")]
            _publish_progress(run_id, "collector", "failed", f"Collection failed: {result.get('error')}")
            record_agent_end(run_id, "collector", False)
            return {
                **state,
                "status": "failed",
                "errors": errors,
                "step_timings": {**state.get("step_timings", {}), "collector": duration},
            }

        _publish_progress(
            run_id, "collector", "success",
            f"Validated {result['valid_rows']}/{result['total_rows']} rows",
            {"valid_rows": result["valid_rows"], "total_rows": result["total_rows"]},
        )
        record_agent_end(run_id, "collector", True)

        return {
            **state,
            "validated_data": result["validated_data"],
            "status": "collecting_done",
            "step_timings": {**state.get("step_timings", {}), "collector": duration},
        }

    except Exception as e:
        duration = time.time() - start
        _publish_progress(run_id, "collector", "failed", str(e))
        record_agent_end(run_id, "collector", False)
        return {
            **state,
            "status": "failed",
            "errors": state.get("errors", []) + [str(e)],
            "step_timings": {**state.get("step_timings", {}), "collector": duration},
        }


def node_estimator(state: PipelineState) -> PipelineState:
    run_id = state["run_id"]
    retry = state.get("retry_count", 0)
    _publish_progress(
        run_id, "estimator", "running",
        f"Estimating carbon sequestration (attempt {retry + 1})...",
    )
    record_agent_start(run_id, "estimator")
    start = time.time()

    try:
        result = run_estimator(
            validated_data=state["validated_data"],
            correction_context=state.get("correction_context", ""),
        )
        duration = time.time() - start

        if result["status"] == "error":
            _publish_progress(run_id, "estimator", "failed", result.get("error", "Estimation failed"))
            record_agent_end(run_id, "estimator", False)
            return {
                **state,
                "status": "failed",
                "errors": state.get("errors", []) + [result.get("error", "")],
                "step_timings": {**state.get("step_timings", {}), "estimator": duration},
            }

        _publish_progress(
            run_id, "estimator", "success",
            f"Estimated {result['total_carbon_tons']:.2f} tCO2 across {result['site_count']} sites",
            {"total_carbon_tons": result["total_carbon_tons"], "site_count": result["site_count"]},
        )
        record_agent_end(run_id, "estimator", True)

        return {
            **state,
            "carbon_estimates": result["estimates"],
            "total_carbon_tons": result["total_carbon_tons"],
            "status": "estimation_done",
            "step_timings": {**state.get("step_timings", {}), "estimator": duration},
        }

    except Exception as e:
        duration = time.time() - start
        _publish_progress(run_id, "estimator", "failed", str(e))
        record_agent_end(run_id, "estimator", False)
        return {
            **state,
            "status": "failed",
            "errors": state.get("errors", []) + [str(e)],
            "step_timings": {**state.get("step_timings", {}), "estimator": duration},
        }


def node_verifier(state: PipelineState) -> PipelineState:
    run_id = state["run_id"]
    _publish_progress(run_id, "verifier", "running", "Verifying carbon estimates and checking anomalies...")
    record_agent_start(run_id, "verifier")
    start = time.time()

    try:
        result = run_verifier(
            validated_data=state["validated_data"],
            carbon_estimates=state["carbon_estimates"],
        )
        duration = time.time() - start

        overall = result.get("overall_result", "FAIL")
        passed = result.get("passed_count", 0)
        failed = result.get("failed_count", 0)

        _publish_progress(
            run_id, "verifier", "success" if overall == "PASS" else "warning",
            f"Verification: {passed} passed, {failed} failed",
            {"overall_result": overall, "passed": passed, "failed": failed},
        )
        record_agent_end(run_id, "verifier", overall == "PASS")

        correction = ""
        if overall == "FAIL" and result.get("failed_sites"):
            correction = (
                f"Previous verification failed for sites: {result['failed_sites']}. "
                f"Please recalculate with corrected ecosystem classification."
            )

        return {
            **state,
            "verification_result": result,
            "status": "verification_done",
            "correction_context": correction,
            "step_timings": {**state.get("step_timings", {}), "verifier": duration},
        }

    except Exception as e:
        duration = time.time() - start
        _publish_progress(run_id, "verifier", "failed", str(e))
        record_agent_end(run_id, "verifier", False)
        return {
            **state,
            "status": "failed",
            "errors": state.get("errors", []) + [str(e)],
            "step_timings": {**state.get("step_timings", {}), "verifier": duration},
        }


def node_registry(state: PipelineState) -> PipelineState:
    run_id = state["run_id"]
    _publish_progress(run_id, "registry", "running", "Registering verified credits on blockchain...")
    record_agent_start(run_id, "registry")
    start = time.time()

    try:
        result = run_registry_agent(
            carbon_estimates=state["carbon_estimates"],
            verification_results=state["verification_result"].get("verification_results", []),
            run_id=run_id,
        )
        duration = time.time() - start

        if result["status"] == "error":
            _publish_progress(run_id, "registry", "failed", result.get("error", "Registry failed"))
            record_agent_end(run_id, "registry", False)
            return {
                **state,
                "status": "failed",
                "errors": state.get("errors", []) + [result.get("error", "")],
                "step_timings": {**state.get("step_timings", {}), "registry": duration},
            }

        _publish_progress(
            run_id, "registry", "success",
            f"Registered {result['registered_count']} credits on blockchain",
            {
                "registered_count": result["registered_count"],
                "total_tons": result["total_registered_tons"],
                "blockchain_results": result["blockchain_results"][:3],
            },
        )
        record_agent_end(run_id, "registry", True)
        record_agent_end(run_id, "total", True)

        _publish_progress(
            run_id, "complete", "success",
            f"Pipeline complete! Total: {state['total_carbon_tons']:.2f} tCO2 registered.",
            {"total_carbon_tons": state["total_carbon_tons"], "run_id": run_id},
        )

        return {
            **state,
            "blockchain_result": result,
            "status": "complete",
            "step_timings": {**state.get("step_timings", {}), "registry": duration},
        }

    except Exception as e:
        duration = time.time() - start
        _publish_progress(run_id, "registry", "failed", str(e))
        record_agent_end(run_id, "registry", False)
        return {
            **state,
            "status": "failed",
            "errors": state.get("errors", []) + [str(e)],
            "step_timings": {**state.get("step_timings", {}), "registry": duration},
        }


def route_after_verifier(state: PipelineState) -> str:
    if state["status"] == "failed":
        return "end_failed"

    verification = state.get("verification_result", {})
    overall = verification.get("overall_result", "FAIL")
    retry_count = state.get("retry_count", 0)

    if overall == "PASS":
        return "registry"
    elif retry_count < MAX_RETRIES:
        state["retry_count"] = retry_count + 1
        return "estimator"
    else:
        return "end_failed"


def route_after_collector(state: PipelineState) -> str:
    return "estimator" if state["status"] != "failed" else "end_failed"


def route_after_estimator(state: PipelineState) -> str:
    return "verifier" if state["status"] != "failed" else "end_failed"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("collector", node_collector)
    graph.add_node("estimator", node_estimator)
    graph.add_node("verifier", node_verifier)
    graph.add_node("registry", node_registry)

    graph.set_entry_point("collector")
    graph.add_conditional_edges(
        "collector",
        route_after_collector,
        {
            "estimator": "estimator",
            "end_failed": END,
        },
    )
    graph.add_conditional_edges(
        "estimator",
        route_after_estimator,
        {
            "verifier": "verifier",
            "end_failed": END,
        },
    )

    graph.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "registry": "registry",
            "estimator": "estimator",
            "end_failed": END,
        },
    )
    graph.add_edge("registry", END)

    return graph.compile()


def run_pipeline(run_id: str, file_path: str) -> Dict[str, Any]:
    app = build_pipeline()
    record_agent_start(run_id, "total")

    initial_state: PipelineState = {
        "run_id": run_id,
        "file_path": file_path,
        "raw_data": None,
        "validated_data": None,
        "carbon_estimates": None,
        "total_carbon_tons": 0.0,
        "verification_result": None,
        "blockchain_result": None,
        "errors": [],
        "retry_count": 0,
        "status": "running",
        "correction_context": "",
        "step_timings": {},
    }

    try:
        final_state = app.invoke(initial_state)
        return dict(final_state)
    except Exception as e:
        logger.error(f"Pipeline {run_id} crashed: {e}")
        _publish_progress(run_id, "pipeline", "failed", f"Pipeline crashed: {e}")
        return {**initial_state, "status": "failed", "errors": [str(e)]}
