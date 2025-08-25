"""Home Assistant integration for WhispyWyser."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Set, Union

import aiohttp

_LOGGER = logging.getLogger(__name__)

RGB_MODES = {"hs", "rgb", "rgbw", "rgbww", "xy"}
BRIGHTNESS_MODES = RGB_MODES | {"brightness", "white"}
FAN_SET_SPEED = 1
COVER_SET_POSITION = 4
MEDIA_PLAYER_PAUSE = 1
MEDIA_PLAYER_VOLUME_SET = 4
MEDIA_PLAYER_NEXT_TRACK = 32

class HomeAssistantError(Exception):
    """Base exception for Home Assistant errors."""
    pass

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

class HomeAssistantClient:
    """Client for interacting with Home Assistant's API."""
    
    def __init__(
        self,
        url: str,
        token: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize the Home Assistant client.
        
        Args:
            url: Base URL of the Home Assistant instance (e.g., 'http://homeassistant:8123')
            token: Long-lived access token
            session: Optional aiohttp ClientSession
        """
        self._base_url = url.rstrip('/')
        self._token = token
        self._headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        self._session = session or aiohttp.ClientSession()
        self._websocket = None
        self._message_id = 1
        self._listeners = {}
        self._event_listeners = {}
        
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def connect(self) -> None:
        """Connect to Home Assistant API and set up WebSocket."""
        if self._session.closed:
            self._session = aiohttp.ClientSession()
            
        await self._setup_websocket()
            
    async def close(self) -> None:
        """Close the connection and clean up resources."""
        if self._websocket is not None:
            await self._websocket.close()
            self._websocket = None
            
        if not self._session.closed:
            await self._session.close()
            
    async def _setup_websocket(self) -> None:
        """Set up WebSocket connection to Home Assistant."""
        ws_url = self._base_url.replace('http', 'ws') + '/api/websocket'
        
        try:
            self._websocket = await self._session.ws_connect(ws_url, heartbeat=55)
            auth_required = await self._websocket.receive_json()
            
            if auth_required['type'] != 'auth_required':
                raise HomeAssistantError('Unexpected message during WebSocket auth')
                
            await self._websocket.send_json({
                'type': 'auth',
                'access_token': self._token
            })
            
            auth_result = await self._websocket.receive_json()
            if auth_result['type'] != 'auth_ok':
                raise HomeAssistantError(f'Authentication failed: {auth_result}')
                
            # Start listening for events
            asyncio.create_task(self._websocket_listener())
            
        except Exception as err:
            _LOGGER.error('WebSocket connection failed: %s', err)
            raise HomeAssistantError(f'WebSocket connection failed: {err}') from err
            
    async def _websocket_listener(self) -> None:
        """Listen for WebSocket messages and dispatch to handlers."""
        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self._handle_websocket_message(data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    _LOGGER.warning('WebSocket connection closed')
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error('WebSocket error: %s', self._websocket.exception())
                    break
                    
        except Exception as err:
            _LOGGER.error('WebSocket listener error: %s', err)
        finally:
            self._websocket = None
            
    async def _handle_websocket_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket messages."""
        if 'id' in data and data['id'] in self._listeners:
            future = self._listeners.pop(data['id'])
            if not future.done():
                if data.get('success', True):
                    future.set_result(data.get('result'))
                else:
                    future.set_exception(HomeAssistantError(data.get('error', {}).get('message', 'Unknown error')))
                    
        elif data.get('type') == 'event':
            event_type = data.get('event', {}).get('event_type')
            if event_type in self._event_listeners:
                for callback in self._event_listeners[event_type]:
                    try:
                        await callback(data['event'])
                    except Exception as err:
                        _LOGGER.error('Error in event handler: %s', err)
                        
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an HTTP request to the Home Assistant API."""
        url = f"{self._base_url}/api/{endpoint.lstrip('/')}"
        
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers'].update(self._headers)
        
        try:
            async with self._session.request(method, url, **kwargs) as resp:
                resp.raise_for_status()
                if resp.status == 204:  # No content
                    return None
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.error('Request failed: %s', err)
            raise HomeAssistantError(f'Request failed: {err}') from err
            
    async def get_entities(self) -> List[Dict[str, Any]]:
        """Get all entities from Home Assistant."""
        return await self._make_request('GET', 'states')
        
    async def get_areas(self) -> List[Dict[str, Any]]:
        """Get all areas from Home Assistant."""
        return await self._make_request('GET', 'config/area_registry')
        
    async def get_entity_registry(self) -> List[Dict[str, Any]]:
        """Get the entity registry from Home Assistant."""
        return await self._make_request('GET', 'config/entity_registry')
        
    async def get_services(self) -> Dict[str, Any]:
        """Get all available services from Home Assistant."""
        return await self._make_request('GET', 'services')
        
    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None,
        target: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Call a service in Home Assistant."""
        data = {}
        if service_data:
            data["service_data"] = service_data
        if target:
            data["target"] = target
            
        return await self._make_request(
            'POST',
            f'services/{domain}/{service}',
            json=data
        )

async def get_hass_info(
    url: str,
    token: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> Things:
    """Get exposed entities and areas from Home Assistant."""
    things = Things()
    
    async with HomeAssistantClient(url, token, session) as client:
        # Get all entities and their states
        entities = await client.get_entities()
        entity_registry = await client.get_entity_registry()
        areas = await client.get_areas()
        services = await client.get_services()
        
        # Process areas
        area_map = {area["area_id"]: area for area in areas}
        
        for area in areas:
            area_names = []
            if "name" in area and area["name"]:
                area_names.append(area["name"])
                
            if area_names:
                things.areas.append(
                    Area(area_id=area["area_id"], names=area_names)
                )
        
        # Process entities
        entity_registry_map = {
            entry["entity_id"]: entry for entry in entity_registry
        }
        
        for entity_state in entities:
            entity_id = entity_state["entity_id"]
            domain = entity_id.split(".", 1)[0]
            
            # Skip entities from ignored domains
            if domain not in {"light", "switch", "media_player", "fan", "cover", "climate"
            }:
                continue
                
            # Get names from entity registry
            names = []
            registry_entry = entity_registry_map.get(entity_id, {})
            
            # Add friendly name if available
            name = registry_entry.get("name") or entity_state.get("attributes", {}).get("friendly_name")
            if name:
                names.append(name)
                
            # Add area name if available
            area_id = registry_entry.get("area_id")
            if area_id and area_id in area_map:
                area = area_map[area_id]
                if "name" in area and area["name"]:
                    names.append(f"{area['name']} {name}" if name else area["name"])
            
            if not names:
                continue
                
            # Create entity with basic info
            entity = Entity(
                entity_id=entity_id,
                names=names,
                domain=domain
            )
            
            # Add domain-specific features
            attributes = entity_state.get("attributes", {})
            
            if domain == "light":
                supported_features = attributes.get("supported_features", 0)
                entity.light_supports_color = bool(supported_features & 16)  # SUPPORT_COLOR
                entity.light_supports_brightness = bool(supported_features & 1)  # SUPPORT_BRIGHTNESS
                
            elif domain == "fan":
                supported_features = attributes.get("supported_features", 0)
                entity.fan_supports_speed = bool(supported_features & FAN_SET_SPEED)
                
            elif domain == "cover":
                supported_features = attributes.get("supported_features", 0)
                entity.cover_supports_position = bool(supported_features & COVER_SET_POSITION)
                
            elif domain == "media_player":
                supported_features = attributes.get("supported_features", 0)
                entity.media_player_supports_pause = bool(supported_features & MEDIA_PLAYER_PAUSE)
                entity.media_player_supports_volume_set = bool(supported_features & MEDIA_PLAYER_VOLUME_SET)
                entity.media_player_supports_next_track = bool(supported_features & MEDIA_PLAYER_NEXT_TRACK)
            
            things.entities.append(entity)
    
    return things
