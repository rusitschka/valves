
from typing import Union

from .cached_entity_wrapper import CachedEntityWrapper
from .const import LOGGER

class TemperatureSensor(CachedEntityWrapper):

    @property
    def value(self) -> Union[float, None]:
        # homematic
        value = self.entity_attribute("current_temperature")
        if value is None:
            # aqara
            value = self.entity_attribute("temperature")
        if value is None:
            return None
        else:
            float_value = float(value)
            return float_value

    def normalize_thermostat_state(self, mode_from="auto", mode_to="heat") -> bool:
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
