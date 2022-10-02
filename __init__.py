import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass:HomeAssistant, config):
    hass.states.async_set('valves.valves_queue', 0)
    await discovery.async_load_platform(hass, "cover", DOMAIN, config[DOMAIN], config)
    return True
