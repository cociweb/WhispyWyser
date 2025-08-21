"""Debug utilities for WhispyWyser."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .homeassistant.models import Entity, Things

_LOGGER = logging.getLogger(__name__)

class EntityDebugLogger:
    """Helper class to log entity information for debugging."""
    
    def __init__(self, output_dir: Union[str, Path] = "./debug"):
        """Initialize the debug logger.
        
        Args:
            output_dir: Directory to store debug files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.entities_file = self.output_dir / "entities.json"
        _LOGGER.info("Entity debug logging enabled. Output directory: %s", self.output_dir)
    
    def log_entities(self, things: Things) -> None:
        """Log discovered entities to a JSON file.
        
        Args:
            things: The Things object containing entities and areas
        """
        try:
            # Convert dataclasses to dictionaries
            entities_data = [self._entity_to_dict(e) for e in things.entities]
            
            # Prepare the output data
            output = {
                "timestamp": datetime.utcnow().isoformat(),
                "entities": entities_data,
                "areas": [{"names": a.names, "area_id": a.area_id} for a in things.areas]
            }
            
            # Write to file
            with open(self.entities_file, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
                
            _LOGGER.debug("Logged %d entities to %s", len(entities_data), self.entities_file)
            
            self._generate_spell_training(things)
            
        except Exception as e:
            _LOGGER.error("Failed to log entities: %s", e, exc_info=True)
    
    def _generate_spell_training(self, things: Things) -> None:
        """Generate spell training data from entities and intents."""
        try:
            # Look for intents in standard locations
            intent_dirs = [
                Path("intents"),  # Local intents
                Path("/config/intents"),  # Home Assistant addon
                Path(__file__).parent.parent / "intents"  # Package intents
            ]
            
            intent_dir = None
            for dir_path in intent_dirs:
                if dir_path.exists() and any(dir_path.glob("*.yaml")):
                    intent_dir = dir_path
                    _LOGGER.debug("Found intents in %s", intent_dir)
                    break
            
            training_file = generate_spell_training(
                things=things,
                output_dir=self.output_dir / "spell_training",
                intent_dir=intent_dir,
                language="en"  # TODO: Make configurable
            )
            _LOGGER.info("Generated spell training data in %s", training_file)
            
        except Exception as e:
            _LOGGER.error("Failed to generate spell training data: %s", e, exc_info=True)
    
    def _entity_to_dict(self, entity: Entity) -> Dict[str, Any]:
        """Convert an Entity to a dictionary, handling dataclass fields."""
        result = {
            "entity_id": getattr(entity, "entity_id", "unknown"),
            "names": entity.names,
            "domain": entity.domain,
        }
        
        # Add all fields that start with 'supports_'
        for field in dir(entity):
            if field.startswith("supports_") or field.startswith("light_") or field.startswith("fan_") or field.startswith("cover_") or field.startswith("media_player_"):
                value = getattr(entity, field, None)
                if value is not None:
                    result[field] = value
        
        return result

def setup_debug_logging(debug: bool = False, output_dir: Optional[str] = None) -> Optional[EntityDebugLogger]:
    """Set up debug logging if enabled.
    
    Args:
        debug: Whether to enable debug logging
        output_dir: Directory to store debug files (default: ./debug)
        
    Returns:
        Configured EntityDebugLogger instance if debug is True, else None
    """
    if not debug:
        return None
        
    # Set up logging level
    logging.basicConfig(level=logging.DEBUG)
    
    # Create and return debug logger
    return EntityDebugLogger(output_dir=output_dir or "./debug")
