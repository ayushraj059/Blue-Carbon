import os
import json
import base64
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

ANALYSIS_PROMPT = """You are an expert coastal ecosystem scientist analyzing satellite/aerial imagery for blue carbon MRV assessment.

Carefully examine this satellite/aerial image of a coastal area.
Return ONLY a valid JSON object — no markdown, no explanation, no code fences:

{
  "ecosystem_type": "<one of: mangrove, seagrass, salt_marsh, tidal_flat, coastal_wetland>",
  "vegetation_density": <float 0.0–1.0, 0=bare/water, 1.0=dense full canopy>,
  "soil_carbon_pct": <estimated float 0.5–15.0 based on ecosystem type and vegetation health>,
  "water_salinity": <estimated float 10–45 PSU based on coastal proximity and ecosystem type>,
  "confidence": <float 0.0–1.0>,
  "description": "<2 sentence description of what you observe>",
  "carbon_indicators": ["list", "of", "specific", "observed", "visual", "features"]
}

Classification guide:
- mangrove: Dense dark-green tree canopy at water/land edges, tannin-stained brownish water, tropical/subtropical coast, prop roots visible
- seagrass: Submerged meadows visible as dark patches in shallow clear coastal water
- salt_marsh: Low halophytic grasses/herbs at coastal margins, often yellowish-green, tidal channels visible
- tidal_flat: Bare mud/sand intertidal areas, minimal vegetation, drainage channels and tidal patterns
- coastal_wetland: Mixed coastal vegetation, transitional estuarine zone, mixed land-water features

Return ONLY the JSON object."""


def _image_to_base64(image_path: str) -> tuple[str, str]:
    """Returns (base64_string, mime_type)."""
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, mime


def _call_groq_vision(b64: str, mime: str) -> str:
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in .env")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                },
                {"type": "text", "text": ANALYSIS_PROMPT},
            ],
        }],
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content


def _parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _clamp(result: dict) -> dict:
    result["vegetation_density"] = max(0.0, min(1.0, float(result.get("vegetation_density", 0.5))))
    result["soil_carbon_pct"] = max(0.5, min(15.0, float(result.get("soil_carbon_pct", 5.0))))
    result["water_salinity"] = max(10.0, min(45.0, float(result.get("water_salinity", 25.0))))
    result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.7))))
    return result


def analyze_satellite_image(image_path: str) -> dict:
    b64, mime = _image_to_base64(image_path)
    raw = _call_groq_vision(b64, mime)
    result = _parse_response(raw)
    return _clamp(result)


def analyze_image_bytes(image_bytes: bytes, content_type: str = "image/jpeg") -> dict:
    suffix = ".png" if "png" in content_type else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name
    try:
        return analyze_satellite_image(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
