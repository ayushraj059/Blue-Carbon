import os
import logging
from typing import List, Dict, Any
from crewai import Agent, Task, Crew

logger = logging.getLogger(__name__)

GROQ_MODEL = "groq/llama-3.3-70b-versatile"

VEGETATION_DENSITY_RANGE = (0.0, 1.0)
SOIL_CARBON_RANGE = (0.5, 15.0)
WATER_SALINITY_RANGE = (10.0, 45.0)
MIN_AREA_HECTARES = 0.0


def _check_anomalies(site: Dict[str, Any]) -> List[str]:
    anomalies = []

    vd = site.get("vegetation_density", 0)
    if not (VEGETATION_DENSITY_RANGE[0] <= vd <= VEGETATION_DENSITY_RANGE[1]):
        anomalies.append(
            f"vegetation_density={vd} out of range [{VEGETATION_DENSITY_RANGE[0]}, {VEGETATION_DENSITY_RANGE[1]}]"
        )

    sc = site.get("soil_carbon_pct", 0)
    if not (SOIL_CARBON_RANGE[0] <= sc <= SOIL_CARBON_RANGE[1]):
        anomalies.append(
            f"soil_carbon_pct={sc} out of range [{SOIL_CARBON_RANGE[0]}, {SOIL_CARBON_RANGE[1]}]"
        )

    ws = site.get("water_salinity", 0)
    if not (WATER_SALINITY_RANGE[0] <= ws <= WATER_SALINITY_RANGE[1]):
        anomalies.append(
            f"water_salinity={ws} out of range [{WATER_SALINITY_RANGE[0]}, {WATER_SALINITY_RANGE[1]}]"
        )

    ah = site.get("area_hectares", 0)
    if ah <= MIN_AREA_HECTARES:
        anomalies.append(f"area_hectares={ah} must be > {MIN_AREA_HECTARES}")

    return anomalies


def run_verifier(
    validated_data: List[Dict[str, Any]],
    carbon_estimates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        if not validated_data:
            return {
                "status": "error",
                "error": "No validated data available for verification",
                "overall_result": "FAIL",
                "verification_results": [],
            }

        if not carbon_estimates:
            return {
                "status": "error",
                "error": "No carbon estimates available for verification",
                "overall_result": "FAIL",
                "verification_results": [],
            }

        estimates_map = {e["site_id"]: e for e in carbon_estimates}

        verification_results = []
        all_passed = True
        failed_sites = []

        for site in validated_data:
            site_id = site["site_id"]
            anomalies = _check_anomalies(site)
            estimate = estimates_map.get(site_id, {})
            carbon_tons = estimate.get("carbon_tons", 0)

            agent = Agent(
                role="Carbon Verification Specialist",
                goal="Verify carbon estimates are scientifically sound and data is anomaly-free",
                backstory=(
                    "You are a senior environmental scientist who validates blue carbon project data. "
                    "You ensure measurements are within acceptable scientific ranges."
                ),
                llm=GROQ_MODEL,
                verbose=False,
                allow_delegation=False,
            )

            anomaly_text = "\n".join(anomalies) if anomalies else "No anomalies detected."
            task = Task(
                description=(
                    f"Verify site {site_id} in {site.get('location', 'unknown')}:\n"
                    f"- vegetation_density: {site.get('vegetation_density')}\n"
                    f"- soil_carbon_pct: {site.get('soil_carbon_pct')}\n"
                    f"- water_salinity: {site.get('water_salinity')}\n"
                    f"- area_hectares: {site.get('area_hectares')}\n"
                    f"- Estimated carbon: {carbon_tons} tCO2\n"
                    f"- Detected anomalies: {anomaly_text}\n\n"
                    f"Assess if the carbon estimate is scientifically reasonable for this site. "
                    f"Respond with VERDICT: PASS or VERDICT: FAIL, and list reason codes."
                ),
                expected_output="VERDICT: PASS or VERDICT: FAIL with reasons.",
                agent=agent,
            )

            crew = Crew(agents=[agent], tasks=[task], verbose=False, memory=False, cache=False)
            crew_result = crew.kickoff()
            verdict_text = str(crew_result)

            site_passed = len(anomalies) == 0 and "VERDICT: FAIL" not in verdict_text

            reason_codes = []
            if anomalies:
                reason_codes.extend([f"ANOMALY: {a}" for a in anomalies])
            if "VERDICT: FAIL" in verdict_text:
                reason_codes.append("LLM_VERIFICATION_FAILED")

            if not site_passed:
                all_passed = False
                failed_sites.append(site_id)

            verification_results.append({
                "site_id": site_id,
                "status": "PASS" if site_passed else "FAIL",
                "anomalies": anomalies,
                "reason_codes": reason_codes,
                "llm_verdict": verdict_text[:500],
            })

        return {
            "status": "success",
            "overall_result": "PASS" if all_passed else "FAIL",
            "verification_results": verification_results,
            "failed_sites": failed_sites,
            "passed_count": sum(1 for r in verification_results if r["status"] == "PASS"),
            "failed_count": sum(1 for r in verification_results if r["status"] == "FAIL"),
        }

    except Exception as e:
        logger.error(f"Verifier agent failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "overall_result": "FAIL",
            "verification_results": [],
        }
