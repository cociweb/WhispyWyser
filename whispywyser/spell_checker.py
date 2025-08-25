"""Spell checking functionality using JamSpell."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, ClassVar

import jamspell

_LOGGER = logging.getLogger(__name__)

@dataclass
class SpellCheckResponse:
    """Response from spell checking."""
    original: str
    corrected: str
    corrected_words: List[Tuple[str, str]]
    
    @property
    def was_corrected(self) -> bool:
        """Return True if any corrections were made."""
        return self.original != self.corrected

class JamSpellChecker:
    """Wrapper around JamSpell for spell checking."""
    
    _instance: ClassVar[Optional[JamSpellChecker]] = None
    
    def __init__(self):
        """Initialize the spell checker."""
        self._model: Optional[jamspell.TSpellCorrector] = None
        self._loaded_models: Dict[str, str] = {}  # language: model_path
    
    @classmethod
    def get_instance(cls) -> JamSpellChecker:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load_model(self, model_path: Path, alphabet_path: Path) -> None:
        """Load a JamSpell model.
        
        Args:
            model_path: Path to the .bin model file
            alphabet_path: Path to the alphabet file
        """
        if not model_path.exists() or not alphabet_path.exists():
            raise FileNotFoundError(
                f"Model files not found. Model: {model_path}, Alphabet: {alphabet_path}"
            )
        
        _LOGGER.info("Loading JamSpell model from %s", model_path)
        
        self._model = jamspell.TSpellCorrector()
        
        if not self._model.LoadLangModel(str(model_path)):
            raise RuntimeError(f"Failed to load JamSpell model from {model_path}")
        
        _LOGGER.info("Successfully loaded JamSpell model")
    
    def correct(self, text: str, language: str = "en") -> SpellCheckResponse:
        """Correct spelling in the input text.
        
        Args:
            text: Input text to correct
            language: Language code (default: en)
            
        Returns:
            SpellCheckResponse with original and corrected text
        """
        if not text.strip():
            return SpellCheckResponse(text, text, [])
            
        if self._model is None:
            _LOGGER.warning("No JamSpell model loaded, returning original text")
            return SpellCheckResponse(text, text, [])
        
        try:
            corrected_text = self._model.FixFragment(text)
            
            # Get the list of corrected words
            corrected_words: List[Tuple[str, str]] = []
            words = text.split()
            corrected_words_list = corrected_text.split()
            
            for orig_word, corrected_word in zip(words, corrected_words_list):
                if orig_word != corrected_word:
                    corrected_words.append((orig_word, corrected_word))
            
            return SpellCheckResponse(
                original=text,
                corrected=corrected_text,
                corrected_words=corrected_words
            )
            
        except Exception as e:
            _LOGGER.error("Error in spell checking: %s", e, exc_info=True)
            # Return original text on error
            return SpellCheckResponse(text, text, [])
