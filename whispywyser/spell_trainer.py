"""Generate training data for JamSpell spell checker."""
from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Set, Tuple, Union

from .homeassistant.models import Entity, Things

_LOGGER = logging.getLogger(__name__)

class SpellTrainer:
    """Generates training data for JamSpell spell checker using Hassil intents."""
    
    def __init__(self, output_dir: Union[str, Path] = "./spell_train"):
        """Initialize the spell trainer."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sentences: Set[str] = set()
        _LOGGER.info("Spell trainer initialized. Output directory: %s", self.output_dir)
    
    def generate_from_entities(self, things: Things) -> None:
        """Generate training sentences from Home Assistant entities."""
        # Add entity names as training data
        for entity in things.entities:
            for name in entity.names:
                self.sentences.add(name.lower())
        
        # Add area names
        for area in things.areas:
            for name in area.names:
                self.sentences.add(name.lower())
    
    def generate_from_hassil(self, intent_dir: Union[str, Path], language: str = "en") -> None:
        """Generate training sentences using Hassil's sample sentences.
        
        Args:
            intent_dir: Directory containing Hassil intent YAML files
            language: Language code (default: en)
        """
        try:
            from hassil.sample import sample_combinations
            
            intent_dir = Path(intent_dir)
            if not intent_dir.exists():
                _LOGGER.warning("Intent directory not found: %s", intent_dir)
                return
                
            # Sample sentences from Hassil intents
            for intent_file in intent_dir.glob("*.yaml"):
                try:
                    for _ in range(10):  # Generate 10 variations per intent
                        result = subprocess.run(
                            [sys.executable, "-m", "hassil.sample", str(intent_file), "--language", language],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        
                        # Parse the output
                        for line in result.stdout.splitlines():
                            try:
                                data = json.loads(line)
                                if "text" in data:
                                    self.sentences.add(data["text"].lower())
                            except json.JSONDecodeError:
                                self.sentences.add(line.strip().lower())
                                
                except subprocess.CalledProcessError as e:
                    _LOGGER.error("Error sampling from %s: %s", intent_file, e.stderr)
                    
        except ImportError:
            _LOGGER.warning("Hassil not installed, skipping intent-based training data")
    
    def save_training_data(self, filename: str = "training.txt") -> Path:
        """Save generated sentences to a file.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to the generated training file
        """
        output_file = self.output_dir / filename
        
        with open(output_file, "w", encoding="utf-8") as f:
            for sentence in sorted(self.sentences):
                if sentence.strip():  # Skip empty lines
                    f.write(f"{sentence}\n")
        
        _LOGGER.info("Saved %d training sentences to %s", len(self.sentences), output_file)
        return output_file

def generate_spell_training(
    things: Things, 
    output_dir: Union[str, Path],
    intent_dir: Optional[Union[str, Path]] = None,
    language: str = "en"
) -> Path:
    """Generate spell training data from Home Assistant entities and Hassil intents.
    
    Args:
        things: The Things object containing entities and areas
        output_dir: Directory to save training data
        intent_dir: Optional directory containing Hassil intent YAML files
        language: Language code (default: en)
        
    Returns:
        Path to the generated training file
    """
    trainer = SpellTrainer(output_dir=output_dir)
    
    # Generate from entity names and areas
    trainer.generate_from_entities(things)
    
    # Generate from Hassil intents if available
    if intent_dir:
        trainer.generate_from_hassil(intent_dir, language=language)
    
    # Save the training data
    return trainer.save_training_data()
