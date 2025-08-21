"""Home Assistant API client for WhispyWyser."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import aiohttp

from .client import HomeAssistantClient, HomeAssistantError
from .models import Area, Entity, Things

__all__ = [
    "HomeAssistantClient",
    "HomeAssistantError",
    "Area",
    "Entity",
    "Things",
    "get_hass_info",
]

async def get_hass_info(
    url: str,
    token: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> Things:
    """Get exposed entities and areas from Home Assistant.
    
    Args:
        url: Base URL of the Home Assistant instance
        token: Long-lived access token
        session: Optional aiohttp ClientSession
        
    Returns:
        Things object containing entities and areas
        
    Raises:
        HomeAssistantError: If there's an error communicating with Home Assistant
    """
    from .client import get_hass_info as _get_hass_info
    return await _get_hass_info(url, token, session)
