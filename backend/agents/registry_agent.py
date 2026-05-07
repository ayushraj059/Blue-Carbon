import os
import logging
import hashlib
from typing import List, Dict, Any
from crewai import Agent, Task, Crew
from blockchain.contract import register_credit

logger = logging.getLogger(__name__)

GROQ_MODEL = "groq/llama-3.3-70b-versatile"


def _make_verification_hash(project_id: str, carbon_tons: float, site_id: str) -> str:
    payload = f"{project_id}:{carbon_tons}:{site_id}"
    return hashlib.sha256(payload.encode()).hexdigest()


def run_registry_agent(
    carbon_estimates: List[Dict[str, Any]],
    verification_results: List[Dict[str, Any]],
    run_id: str,
) -> Dict[str, Any]:
    try:
        passed_sites = {
            r["site_id"] for r in verification_results if r["status"] == "PASS"
        }

        estimates_to_register = [
            e for e in carbon_estimates if e["site_id"] in passed_sites
        ]

        if not estimates_to_register:
            return {
                "status": "error",
                "error": "No verified sites to register",
                "blockchain_results": [],
            }

        blockchain_results = []

        for estimate in estimates_to_register:
            site_id = estimate["site_id"]
            carbon_tons = estimate["carbon_tons"]
            project_id = f"{run_id[:8]}-{site_id}"
            verification_hash = _make_verification_hash(project_id, carbon_tons, site_id)

            try:
                tx_result = register_credit(
                    project_id=project_id,
                    carbon_tons=carbon_tons,
                    verification_hash=verification_hash,
                )

                blockchain_results.append({
                    "project_id": project_id,
                    "site_id": site_id,
                    "carbon_tons": carbon_tons,
                    "tx_hash": tx_result["tx_hash"],
                    "block_number": tx_result["block_number"],
                    "status": tx_result["status"],
                    "gas_used": tx_result.get("gas_used", 0),
                })

            except Exception as e:
                logger.error(f"Failed to register site {site_id} on blockchain: {e}")
                blockchain_results.append({
                    "project_id": project_id,
                    "site_id": site_id,
                    "carbon_tons": carbon_tons,
                    "tx_hash": None,
                    "block_number": None,
                    "status": "failed",
                    "error": str(e),
                })

        agent = Agent(
            role="Blockchain Registry Specialist",
            goal="Confirm successful registration of carbon credits on the blockchain",
            backstory=(
                "You are a blockchain integration specialist who manages carbon credit registration "
                "on the Polygon network for blue carbon projects."
            ),
            llm=GROQ_MODEL,
            verbose=False,
            allow_delegation=False,
        )

        successful = [r for r in blockchain_results if r["status"] == "success"]
        summary = (
            f"Registered {len(successful)}/{len(estimates_to_register)} sites on blockchain. "
            f"Total carbon: {sum(r['carbon_tons'] for r in successful):.3f} tCO2"
        )

        task = Task(
            description=f"Confirm this blockchain registration summary: {summary}",
            expected_output="Confirmation of blockchain registration with key details.",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False, memory=False, cache=False)
        crew.kickoff()

        return {
            "status": "success",
            "blockchain_results": blockchain_results,
            "registered_count": len(successful),
            "total_registered_tons": sum(r["carbon_tons"] for r in successful),
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Registry agent failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "blockchain_results": [],
        }
