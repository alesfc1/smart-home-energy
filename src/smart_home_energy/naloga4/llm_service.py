"""Kliče ponudnika OpenRouter in pošlje zahtevo jezikovnemu modelu ter preveri strukturirani odgovor"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .models import EnergyAnalysis

load_dotenv()

def analyze_energy(prompt: str) -> EnergyAnalysis:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Manjka OPENROUTER_API_KEY. Dodaj ga v datoteko .env.")

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    response = client.chat.completions.create(
        model="nvidia/nemotron-3.5-super-vl:free",
        messages=[
            {"role": "system", "content": "Vrni samo veljaven JSON z zahtevanimi polji."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Ponudnik LLM je vrnil prazen odgovor.")
    return EnergyAnalysis.model_validate(json.loads(content))
