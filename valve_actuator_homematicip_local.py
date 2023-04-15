from typing import Union

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .const import LOGGER
from .valve_actuator import ValveActuator

class ValveActuatorHomematicIPLocal(ValveActuator):
    def __init__(self, home_assistant:HomeAssistant, valve_config:dict):
        super().__init__(home_assistant, valve_config)
        self._device_id = None

    @property
    def value(self) -> Union[float, None]:
        value = self.entity_attribute("current_temperature")
        return None if value is None else float(value)

    @property
    def valve_position(self) -> Union[float, None]:
        valve_position_id = self._valve_config.get("valve_position", None)
        if valve_position_id is None:
            raise ValueError("valve_position missing in config!")
        valve_position_state = self._home_assistant.states.get(valve_position_id)
        if valve_position_state is None:
            LOGGER.info("%s: valve_position valve_position_state is None",
                            self._entity_name)
            return None
        valve_position = valve_position_state.state
        # LOGGER.info("%s: valve_position valve_position is %s",
        #                 self._entity_name, valve_position)
        return None if valve_position is None else float(valve_position)

    async def async_set_valve_position(self, value:float, urgent:bool) -> bool:
        if self._device_id is None:
            registry = entity_registry.async_get(self._home_assistant)
            entry = registry.async_get(self._entity_name)
            self._device_id = entry.device_id
            LOGGER.info("%s: Got device_id %s",
                    self._entity_name, self._device_id)

        data = {
            "device_id": self._device_id,
            "paramset_key": "MASTER",
            "paramset": {
                "VALVE_MAXIMUM_POSITION": value
            },
            "rx_mode": "BURST" if urgent else "WAKEUP"
        }
        return await self._home_assistant.services.async_call(
                "homematicip_local",
                "put_paramset",
                data,
                blocking=True)

    def normalize_valve_state(self) -> bool:
        if not self.available:
            return False
        res = self.normalize_hvac_mode()
        if self._home_assistant.states.get("input_boolean.heating_on").state == "on":
            target_temp = 30.5
        else:
            target_temp = 4.5
        return res or self.normalize_target_temp(target_temp)
