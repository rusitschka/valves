
from typing import Union


from homeassistant.core import HomeAssistant

from .valve_actuator_bosch import ValveActuatorBosch
from .valve_actuator_eurotronic import ValveActuatorEurotronic
from .valve_actuator_homematic import ValveActuatorHomematic
from .valve_actuator_homematicip_local import ValveActuatorHomematicIPLocal
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
    def type(self) -> str:
        return self._valve_config.get("type", "auto")

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

    async def async_set_valve_position(self, value:float, urgent:bool) -> bool:
        valve_actuator = self.__get_valve_actuator()
        if valve_actuator is not None:
            return await valve_actuator.async_set_valve_position(value, urgent)
        else:
            return False

    def __get_valve_actuator(self):
        if self._valve_actuator is None:
            if (self.type == "auto" and self.entity_attribute("eurotronic_system_mode") is not None
                    or self.type == "eurotronic"):
                self._valve_actuator = ValveActuatorEurotronic(
                        self._home_assistant, self._valve_config)
            elif (self.type == "auto" and self.entity_attribute("interface") == "rf"
                    or self.type == "homematic"):
                self._valve_actuator = ValveActuatorHomematic(
                        self._home_assistant, self._valve_config)
            elif (self.type == "auto"
                    and self.entity_attribute("interface_id") is not None
                    and self.entity_attribute("interface_id").endswith("-BidCos-RF")
                    or self.type == "homematicip_local"):
                self._valve_actuator = ValveActuatorHomematicIPLocal(
                        self._home_assistant, self._valve_config)
            elif self.type == "bosch":
                self._valve_actuator = ValveActuatorBosch(
                        self._home_assistant, self._valve_config)
            elif self.type == "shelly":
                self._valve_actuator = ValveActuatorShelly(
                        self._home_assistant, self._valve_config)
        return self._valve_actuator
