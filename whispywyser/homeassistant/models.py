"""Data models for Home Assistant integration."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional

@dataclass
class Entity:
    """Home Assistant entity."""

    entity_id: str
    names: List[str]
    domain: str
    
    # Domain-specific features
    light_supports_color: Optional[bool] = None
    light_supports_brightness: Optional[bool] = None
    fan_supports_speed: Optional[bool] = None
    cover_supports_position: Optional[bool] = None
    media_player_supports_pause: Optional[bool] = None
    media_player_supports_volume_set: Optional[bool] = None
    media_player_supports_next_track: Optional[bool] = None
    _hash: str = ""

    def get_hash(self) -> str:
        """Get a stable hash for this entity."""
        if not self._hash:
            hasher = hashlib.sha256()
            hasher.update(self.entity_id.encode("utf-8"))
            hasher.update(self.domain.encode("utf-8"))

            for supports_field in fields(self):
                if "supports" not in supports_field.name:
                    continue

                supports_value = getattr(self, supports_field.name)
                if supports_value is None:
                    continue

                hasher.update(f"{supports_field.name}={supports_value}".encode("utf-8"))

            for name in sorted(self.names):
                hasher.update(name.encode("utf-8"))

            self._hash = hasher.hexdigest()

        return self._hash

@dataclass
class Area:
    """Home Assistant area."""

    area_id: str
    names: List[str]
    _hash: str = ""

    def get_hash(self) -> str:
        """Get a stable hash for this area."""
        if not self._hash:
            hasher = hashlib.sha256()
            hasher.update(self.area_id.encode("utf-8"))

            for name in sorted(self.names):
                hasher.update(name.encode("utf-8"))

            self._hash = hasher.hexdigest()

        return self._hash

@dataclass
class Things:
    """Exposed things in Home Assistant."""

    entities: List[Entity] = field(default_factory=list)
    areas: List[Area] = field(default_factory=list)
    _hash: str = ""

    def get_hash(self) -> str:
        """Get a stable hash for all the things."""
        if not self._hash:
            hasher = hashlib.sha256()
            
            for entity in sorted(self.entities, key=lambda e: e.entity_id):
                hasher.update(entity.get_hash().encode("utf-8"))
                
            for area in sorted(self.areas, key=lambda a: a.area_id):
                hasher.update(area.get_hash().encode("utf-8"))
                
            self._hash = hasher.hexdigest()
            
        return self._hash

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for JSON serialization."""
        return {
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "names": e.names,
                    "domain": e.domain,
                    "light_supports_color": e.light_supports_color,
                    "light_supports_brightness": e.light_supports_brightness,
                    "fan_supports_speed": e.fan_supports_speed,
                    "cover_supports_position": e.cover_supports_position,
                    "media_player_supports_pause": e.media_player_supports_pause,
                    "media_player_supports_volume_set": e.media_player_supports_volume_set,
                    "media_player_supports_next_track": e.media_player_supports_next_track,
                }
                for e in self.entities
            ],
            "areas": [
                {"area_id": a.area_id, "names": a.names} for a in self.areas
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Things':
        """Create from a dictionary."""
        things = cls()
        
        # Add entities
        for entity_data in data.get("entities", []):
            entity = Entity(
                entity_id=entity_data["entity_id"],
                names=entity_data["names"],
                domain=entity_data["domain"],
                light_supports_color=entity_data.get("light_supports_color"),
                light_supports_brightness=entity_data.get("light_supports_brightness"),
                fan_supports_speed=entity_data.get("fan_supports_speed"),
                cover_supports_position=entity_data.get("cover_supports_position"),
                media_player_supports_pause=entity_data.get("media_player_supports_pause"),
                media_player_supports_volume_set=entity_data.get("media_player_supports_volume_set"),
                media_player_supports_next_track=entity_data.get("media_player_supports_next_track"),
            )
            things.entities.append(entity)
            
        # Add areas
        for area_data in data.get("areas", []):
            area = Area(
                area_id=area_data["area_id"],
                names=area_data["names"]
            )
            things.areas.append(area)
            
        return things
