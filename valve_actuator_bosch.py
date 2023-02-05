
from typing import Union

from .valve_actuator import ValveActuator

class ValveActuatorBosch(ValveActuator):

    @property
    def value(self) -> Union[float, None]:
        value = self.entity_attribute("local_temperature")
        return None if value is None else float(value)

    @property
    def valve_position(self) -> Union[float, None]:
        valve_position = self.entity_attribute("pi_heating_demand")
        #valve_position = self.entity_attribute("valve_position")
        #if valve_position is not None:
        #    valve_position = int(valve_position) * 100 / 255
        return None if valve_position is None else float(valve_position)

    async def async_set_valve_position(self, value:float, urgent:bool) -> bool:
        # This currently does not work. zigb2mqtt documentation seems wrong.
        return await self._home_assistant.services.async_call("mqtt", "publish", {
            'topic': f"zigbee2mqtt/{self.stripped_entity_name}/set",
            'payload': f"{{ \"pi_heating_demand\": {int(value)} }}"
        }, blocking=True)

    def normalize_valve_state(self) -> bool:
        if not self.available:
            return False
        res = self.normalize_hvac_mode("auto", "heat")
        #res = res or self.normalize_target_temp(30)
        # "Poll" local temperature
        # self._home_assistant.services.call('mqtt', 'publish', {
        #     'topic': f"zigbee2mqtt/{self.stripped_entity_name}/get",
        #     'payload': "{\"local_temperature\": \"\"}"
        # })
        return res
