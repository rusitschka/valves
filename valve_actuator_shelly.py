
from typing import Union

from .valve_actuator import ValveActuator

class ValveActuatorShelly(ValveActuator):
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
            return None
        valve_position = valve_position_state.state
        return None if valve_position is None else float(valve_position)

    def set_valve_position(self, value:float, urgent:bool):
        valve_position_id = self._valve_config.get("valve_position", None)
        if valve_position_id is None:
            raise ValueError("valve_position missing in config!")
        self._home_assistant.services.call("number", "set_value", {
            'entity_id': valve_position_id,
            'value': value
        })

    def normalize_valve_state(self) -> bool:
        # Nothing to normalize for Shelly
        return False
