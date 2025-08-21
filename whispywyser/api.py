"""API endpoints for WhispyWyser services."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .spell_checker import JamSpellChecker, SpellCheckRequest, SpellCheckResponse

_LOGGER = logging.getLogger(__name__)

class SpellCheckRequestModel(BaseModel):
    """Request model for spell checking."""
    text: str = Field(..., description="Text to check and correct")
    language: str = Field(default="en", description="Language code (default: en)")

class SpellCheckResponseModel(BaseModel):
    """Response model for spell checking."""
    original: str = Field(..., description="Original input text")
    corrected: str = Field(..., description="Corrected text")
    corrected_words: list[tuple[str, str]] = Field(
        default_factory=list,
        description="List of (original, corrected) word pairs"
    )

def create_app(
    spell_checker: Optional[JamSpellChecker] = None,
    model_path: Optional[Path] = None,
    alphabet_path: Optional[Path] = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="WhispyWyser API",
        description="API for WhispyWyser services",
        version="0.1.0",
    )
    
    # Initialize the spell checker if not provided
    if spell_checker is None:
        spell_checker = JamSpellChecker.get_instance()
        if model_path is None:
            model_path = Path("models/jamspell.bin")
        if alphabet_path is None:
            alphabet_path = Path("models/alphabet.txt")
        
        try:
            spell_checker.load_model(model_path, alphabet_path)
        except Exception as e:
            _LOGGER.warning("Failed to load spell checker model: %s", e)
    
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "ok"}
    
    @app.post("/api/spell/check", response_model=SpellCheckResponseModel)
    async def check_spelling(request: SpellCheckRequestModel) -> SpellCheckResponseModel:
        """Check and correct spelling in the input text."""
        try:
            response = spell_checker.correct(
                text=request.text,
                language=request.language
            )
            
            return SpellCheckResponseModel(
                original=response.original,
                corrected=response.corrected,
                corrected_words=response.corrected_words
            )
        except Exception as e:
            _LOGGER.error("Error in spell checking: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    return app

def run_api_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    model_path: Optional[Path] = None,
    alphabet_path: Optional[Path] = None,
    reload: bool = False
) -> None:
    """Run the API server."""
    app = create_app(model_path=model_path, alphabet_path=alphabet_path)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=reload
    )
