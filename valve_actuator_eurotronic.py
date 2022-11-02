
from typing import Union

from .valve_actuator import ValveActuator
from .const import LOGGER

class ValveActuatorEurotronic(ValveActuator):

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
        return await self._home_assistant.services.async_call("mqtt", "publish", {
            'topic': f"zigbee2mqtt/{self.stripped_entity_name}/set/eurotronic_valve_position",
            'payload': int(value * 255 / 100)
            #'topic': "zigbee2mqtt/%s/set" % self.stripped_entity_name,
            #'payload': "{\"valve_position\": %s}" % int(value * 255 / 100)
        }, blocking=True)

    def normalize_valve_state(self) -> bool:
        if not self.available:
            return False
        res = self.normalize_hvac_mode("heat", "auto")
        res = res or self.normalize_target_temp(30)
        # "Poll" local temperature
        self._home_assistant.services.call('mqtt', 'publish', {
            'topic': f"zigbee2mqtt/{self.stripped_entity_name}/get",
            'payload': "{\"local_temperature\": \"\"}"
        })
        # if int(self.entity_attribute("trv_mode")) != 1:
        #     self._home_assistant.services.call('mqtt', 'publish', {
        #         'topic': "zigbee2mqtt/%s/set" % self.stripped_entity_name,
        #         'payload': "{\"trv_mode\": 1}"
        #     })
        #     LOGGER.info("%s: trv_mode not 1 - Set eurotronics trv_mode to manual (1)" ,
        #            self._entity_name)
        #     return True
        if float(self.value) < 5.0:
            LOGGER.info("%s: Work-around strange Eurotronics temp %f",
                    self._entity_name, self.value)
            # 0.01 by flipping target temp
            self._home_assistant.services.call('mqtt', 'publish', {
                'topic': f"zigbee2mqtt/{self.stripped_entity_name}/set/eurotronic_trv_mode",
                'payload': 2
                #'topic': "zigbee2mqtt/%s/set" % self.stripped_entity_name,
                #'payload': "{\"trv_mode\": 2}"
            })
            return self.normalize_target_temp(29)
        if float(self.entity_attribute('pi_heating_demand')) > 80:
            self._home_assistant.services.call('mqtt', 'publish', {
                'topic': f"zigbee2mqtt/{self.stripped_entity_name}/set/eurotronic_trv_mode",
                'payload': 1
                #'topic': "zigbee2mqtt/%s/set" % self.stripped_entity_name,
                #'payload': "{\"trv_mode\": 1}"
            })
            LOGGER.info("%s: Heating to high - set eurotronics trv_mode to manual (1)",
                    self._entity_name)
            return True
        return res
