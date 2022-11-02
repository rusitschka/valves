
from typing import Union

from .valve_actuator import ValveActuator

class ValveActuatorHomematic(ValveActuator):
    @property
    def value(self) -> Union[float, None]:
        value = self.entity_attribute("current_temperature")
        return None if value is None else float(value)

    @property
    def valve_position(self) -> Union[float, None]:
        # homematic
        valve_position = self.entity_attribute("valve")
        return None if valve_position is None else float(valve_position)

    async def async_set_valve_position(self, value:float, urgent:bool) -> bool:
        data = {
            "interface": self.entity_attribute("interface"),
            "address": self.entity_attribute("id"),
            "paramset_key": "MASTER",
            "paramset": {
                "VALVE_MAXIMUM_POSITION": value
            },
            "rx_mode": "BURST" if urgent else "WAKEUP"
        }
        return await self._home_assistant.services.async_call(
                "homematic",
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
