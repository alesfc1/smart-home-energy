"""Oblika odgovora od LLM """

from pydantic import BaseModel
from typing import Literal


class Recommendation(BaseModel):
    title: str
    description: str
    priority: Literal["low", "medium", "high"]


class EnergyAnalysis(BaseModel):
    summary: str
    consumption_analysis: str
    weather_impact: str
    recommendations: list[Recommendation]
    conclusion: str