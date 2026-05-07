import os
import logging
from typing import List, Dict, Any
from crewai import Agent, Task, Crew
from rag.retriever import get_ecosystem_multiplier

logger = logging.getLogger(__name__)

GROQ_MODEL = "groq/llama-3.3-70b-versatile"


def calculate_carbon(
    area_hectares: float,
    vegetation_density: float,
    soil_carbon_pct: float,
    ecosystem_multiplier: float,
) -> float:
    return area_hectares * vegetation_density * soil_carbon_pct * 3.67 * ecosystem_multiplier


def run_estimator(
    validated_data: List[Dict[str, Any]],
    correction_context: str = "",
) -> Dict[str, Any]:
    try:
        if not validated_data:
            return {
                "status": "error",
                "error": "No validated data available for estimation",
                "estimates": [],
                "total_carbon_tons": 0.0,
            }

        estimates = []

        for site in validated_data:
            rag_result = get_ecosystem_multiplier(
                location=site["location"],
                vegetation_density=site["vegetation_density"],
            )

            ecosystem_type = rag_result["ecosystem_type"]
            multiplier = rag_result["ecosystem_multiplier"]

            site_context = (
                f"Site {site['site_id']} in {site['location']}: "
                f"vegetation_density={site['vegetation_density']}, "
                f"soil_carbon_pct={site['soil_carbon_pct']}, "
                f"water_salinity={site['water_salinity']}, "
                f"area_hectares={site['area_hectares']}. "
                f"RAG suggests ecosystem type: {ecosystem_type} with multiplier {multiplier}."
            )

            agent = Agent(
                role="Carbon Estimation Expert",
                goal="Accurately estimate blue carbon sequestration for coastal sites",
                backstory=(
                    "You are an IPCC-certified carbon scientist specializing in blue carbon ecosystems. "
                    "You analyze coastal site data to determine ecosystem type and calculate carbon sequestration."
                ),
                llm=GROQ_MODEL,
                verbose=False,
                allow_delegation=False,
            )

            correction_note = f"\nCorrection context: {correction_context}" if correction_context else ""

            task = Task(
                description=(
                    f"Analyze this coastal site and confirm the ecosystem classification:\n"
                    f"{site_context}{correction_note}\n"
                    f"Based on location name, vegetation density, and salinity, confirm or adjust "
                    f"the ecosystem type. Return ecosystem type and reasoning in 2-3 sentences."
                ),
                expected_output="Ecosystem type confirmation with brief reasoning.",
                agent=agent,
            )

            crew = Crew(agents=[agent], tasks=[task], verbose=False, memory=False, cache=False)
            crew_result = crew.kickoff()
            llm_reasoning = str(crew_result)

            carbon_tons = calculate_carbon(
                area_hectares=site["area_hectares"],
                vegetation_density=site["vegetation_density"],
                soil_carbon_pct=site["soil_carbon_pct"],
                ecosystem_multiplier=multiplier,
            )

            estimates.append({
                "site_id": site["site_id"],
                "location": site["location"],
                "carbon_tons": round(carbon_tons, 3),
                "ecosystem_type": ecosystem_type,
                "ecosystem_multiplier": multiplier,
                "area_hectares": site["area_hectares"],
                "rag_confidence": rag_result.get("confidence", 0.0),
                "llm_reasoning": llm_reasoning,
            })

        total_carbon = sum(e["carbon_tons"] for e in estimates)

        return {
            "status": "success",
            "estimates": estimates,
            "total_carbon_tons": round(total_carbon, 3),
            "site_count": len(estimates),
        }

    except Exception as e:
        logger.error(f"Estimator agent failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "estimates": [],
            "total_carbon_tons": 0.0,
        }
