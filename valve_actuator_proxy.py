
from typing import Union


from homeassistant.core import HomeAssistant

from .valve_actuator_eurotronic import ValveActuatorEurotronic
from .valve_actuator_homematic import ValveActuatorHomematic
from .valve_actuator_shelly import ValveActuatorShelly

class ValveActuatorProxy:

    def __init__(self, home_assistant:HomeAssistant, valve_config:dict):
        self._home_assistant = home_assistant
        self._valve_config = valve_config
        self._entity_name = valve_config["id"]
        self._valve_actuator = None

    @property
    def entity_name(self):
        return self._entity_name

    @property
    def entity(self):
        return self._home_assistant.states.get(self._entity_name)

    def entity_attribute(self, attribute_name:str):
        return None if self.entity is None else self.entity.attributes.get(attribute_name)

    @property
    def available(self) -> bool:
        valve_actuator = self.__get_valve_actuator()
        return False if valve_actuator is None else valve_actuator.available

    @property
    def value(self) -> Union[float, None]:
        valve_actuator = self.__get_valve_actuator()
        return None if valve_actuator is None else valve_actuator.value

    @property
    def valve_position(self) -> Union[float, None]:
        valve_actuator = self.__get_valve_actuator()
        return None if valve_actuator is None else valve_actuator.valve_position

    def normalize_valve_state(self) -> bool:
        valve_actuator = self.__get_valve_actuator()
        return False if valve_actuator is None else valve_actuator.normalize_valve_state()

    def set_valve_position(self, value:float, urgent:bool):
        valve_actuator = self.__get_valve_actuator()
        if valve_actuator is not None:
            valve_actuator.set_valve_position(value, urgent)

    def __get_valve_actuator(self):
        if self._valve_actuator is None:
            if self.entity_attribute("eurotronic_system_mode") is not None:
                self._valve_actuator = ValveActuatorEurotronic(
                        self._home_assistant, self._valve_config)
            elif self.entity_attribute("interface") == "rf":
                self._valve_actuator = ValveActuatorHomematic(
                        self._home_assistant, self._valve_config)
            elif self.entity_attribute("target_temp_step") is not None:
                self._valve_actuator = ValveActuatorShelly(
                        self._home_assistant, self._valve_config)
        return self._valve_actuator
