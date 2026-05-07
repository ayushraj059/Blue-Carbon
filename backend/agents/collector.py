import os
import pandas as pd
import logging
from typing import List, Dict, Any
from crewai import Agent, Task, Crew

logger = logging.getLogger(__name__)

GROQ_MODEL = "groq/llama-3.3-70b-versatile"

REQUIRED_COLUMNS = [
    "site_id", "location", "vegetation_density",
    "soil_carbon_pct", "water_salinity", "area_hectares", "measurement_date",
]


def run_collector(file_path: str) -> Dict[str, Any]:
    try:
        df = pd.read_csv(file_path)

        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            return {
                "status": "error",
                "error": f"Missing required columns: {missing_cols}",
                "validated_data": [],
            }

        df = df[REQUIRED_COLUMNS].copy()

        validation_errors = []
        valid_rows = []

        for idx, row in df.iterrows():
            row_errors = []
            try:
                record = {
                    "site_id": str(row["site_id"]).strip(),
                    "location": str(row["location"]).strip(),
                    "vegetation_density": float(row["vegetation_density"]),
                    "soil_carbon_pct": float(row["soil_carbon_pct"]),
                    "water_salinity": float(row["water_salinity"]),
                    "area_hectares": float(row["area_hectares"]),
                    "measurement_date": str(row["measurement_date"]).strip(),
                }

                if not record["site_id"]:
                    row_errors.append("site_id is empty")
                if not record["location"]:
                    row_errors.append("location is empty")
                if record["area_hectares"] <= 0:
                    row_errors.append("area_hectares must be > 0")

                if row_errors:
                    validation_errors.append({
                        "row": idx + 1,
                        "site_id": row.get("site_id", "unknown"),
                        "errors": row_errors,
                    })
                else:
                    valid_rows.append(record)

            except (ValueError, TypeError) as e:
                validation_errors.append({
                    "row": idx + 1,
                    "site_id": row.get("site_id", "unknown"),
                    "errors": [f"Type conversion error: {str(e)}"],
                })

        agent = Agent(
            role="Data Collection Specialist",
            goal="Validate and parse coastal environmental data from CSV files",
            backstory=(
                "You are an expert in environmental data validation for blue carbon projects. "
                "You ensure data quality and completeness before processing."
            ),
            llm=GROQ_MODEL,
            verbose=False,
            allow_delegation=False,
        )

        summary = f"Parsed {len(df)} rows. Valid: {len(valid_rows)}. Errors: {len(validation_errors)}."
        if validation_errors:
            summary += f" Error rows: {[e['row'] for e in validation_errors]}"

        task = Task(
            description=f"Review this data collection summary and confirm validity: {summary}",
            expected_output="Brief confirmation that data has been reviewed with any concerns noted.",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False, memory=False, cache=False)
        crew_result = crew.kickoff()
        agent_review = str(crew_result)

        return {
            "status": "success" if valid_rows else "error",
            "total_rows": len(df),
            "valid_rows": len(valid_rows),
            "error_rows": len(validation_errors),
            "validated_data": valid_rows,
            "validation_errors": validation_errors,
            "agent_review": agent_review,
        }

    except Exception as e:
        logger.error(f"Collector agent failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "validated_data": [],
        }
