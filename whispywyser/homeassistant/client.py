"""Home Assistant WebSocket and REST API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable

import aiohttp

from .models import Area, Entity, Things

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

def validate_ha_token(token: Optional[str]) -> str:
    """Validate Home Assistant token.
    
    Args:
        token: Token to validate (can be None)
        
    Returns:
        Validated token
        
    Raises:
        HomeAssistantError: If token is invalid or not provided
    """
    if not token:
        raise HomeAssistantError(
            "No Home Assistant token provided. "
            "Please set the HA_TOKEN environment variable."
        )
        
    if not isinstance(token, str) or len(token.strip()) < 10:  # Basic validation
        raise HomeAssistantError("Invalid Home Assistant token format")
        
    return token.strip()


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
            
        Raises:
            HomeAssistantError: If token is invalid
        """
        self._base_url = url.rstrip('/')
        self._token = validate_ha_token(token)
        self._headers = {
            'Authorization': f'Bearer {self._token}',
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
            
    async def get_entities(self, debug_logger = None) -> List[Dict[str, Any]]:
        """Get all entities from Home Assistant.
        
        Args:
            debug_logger: Optional debug logger instance for logging discovered entities
            
        Returns:
            List of entity states
        """
        entities = await self._make_request('GET', 'states')
        
        # Log entities if debug logger is provided
        if debug_logger and hasattr(debug_logger, 'log_entities'):
            try:
                # Create a Things object with the discovered entities
                things = await self.get_hass_info()
                debug_logger.log_entities(things)
            except Exception as e:
                _LOGGER.warning("Failed to log entities for debugging: %s", e)
                
        return entities
        
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

    def subscribe_events(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> Callable[[], None]:
        """Subscribe to Home Assistant events.
        
        Args:
            event_type: Event type to subscribe to
            callback: Async callback to call when event is received
            
        Returns:
            Function to unsubscribe
        """
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
            
        self._event_listeners[event_type].append(callback)
        
        def unsubscribe():
            if event_type in self._event_listeners and callback in self._event_listeners[event_type]:
                self._event_listeners[event_type].remove(callback)
                
        return unsubscribe

async def get_hass_info(
    url: str,
    token: str,
    session: Optional[aiohttp.ClientSession] = None,
    debug_logger: Optional[Any] = None,
) -> Things:
    """Get exposed entities and areas from Home Assistant."""
    things = Things()
    
    async with HomeAssistantClient(url, token, session) as client:
        # Get all entities and their states
        entities = await client.get_entities(debug_logger=debug_logger)
        entity_registry = await client.get_entity_registry()
        areas = await client.get_areas()
        
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
