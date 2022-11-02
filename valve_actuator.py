
from typing import Union

from homeassistant.core import HomeAssistant

from .cached_entity_wrapper import CachedEntityWrapper
from .const import LOGGER

class ValveActuator(CachedEntityWrapper):
    def __init__(self, home_assistant:HomeAssistant, valve_config:dict):
        super().__init__(home_assistant, valve_config["id"])
        self._valve_config = valve_config

    @property
    def stripped_entity_name(self):
        stripped_entity_name = self.entity_name
        prefix = "climate."
        if stripped_entity_name.startswith(prefix):
            stripped_entity_name = stripped_entity_name[len(prefix):]
        return stripped_entity_name

    @property
    def value(self) -> Union[float, None]:
        raise NotImplementedError()

    @property
    def valve_position(self) -> Union[float, None]:
        raise NotImplementedError()

    async def async_set_valve_position(self, value:float, urgent:bool) -> bool:
        raise NotImplementedError()

    def normalize_valve_state(self) -> bool:
        raise NotImplementedError()

    def normalize_hvac_mode(self, mode_from="auto", mode_to="heat") -> bool:
        if not self.available:
            return False
        if self.entity.state == mode_from:
            self._home_assistant.services.call('climate', 'set_hvac_mode', {
                'entity_id' : self.entity_name,
                'hvac_mode': mode_to
            })
            LOGGER.info("%s: Normalized hvac_mode state to %s", self._entity_name, mode_to)
            return True
        else:
            return False

    def normalize_target_temp(self, target_temp) -> bool:
        if self.entity_attribute('temperature') != target_temp:
            self._home_assistant.services.call('climate', 'set_temperature', {
                'entity_id' : self.entity_name,
                'temperature': target_temp
            })
            LOGGER.info("%s: Normalized temperature state", self._entity_name)
            return True
        else:
            return False
