# -*- coding: utf-8 -*-
"""
Created on Tue Jan 20 20:43:05 2026

@author: Raymond
"""

# src/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import os

from src.agent import MarketAnalysisAgent  # <-- adapte le chemin

app = FastAPI(title="E-commerce Market Analysis API", version="1.0.0")

class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query, e.g., 'iphone 15'")
    output_file: Optional[str] = Field(None, description="Optional path to write the HTML report")
    include_debug: bool = Field(False, description="Include debug section in the HTML report")

class AnalyzeResponse(BaseModel):
    query: str
    report_path: Optional[str] = None
    analysis: Dict[str, Any]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    try:
        agent = MarketAnalysisAgent()
        result = agent.run(req.query)


        # Si ton agent renvoie déjà report_path, garde-le.
        report_path = result.get("report_path")

        # Sinon, si tu veux forcer l’écriture ici :
        if req.output_file:
            os.makedirs(os.path.dirname(req.output_file) or ".", exist_ok=True)
            # Selon ton code actuel: soit agent génère le HTML, soit ReportGenerator le fait.
            # Ici on suppose que result contient "report_html"
            if "report_html" in result:
                with open(req.output_file, "w", encoding="utf-8") as f:
                    f.write(result["report_html"])
                report_path = req.output_file

        return AnalyzeResponse(query=req.query, report_path=report_path, analysis=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
