
import asyncio

from datetime import datetime
from collections import OrderedDict
from typing import Union

from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from .const import (
    LOGGER,
    QUEUE_INTERVAL_TIMEDELTA
)
from .valve_actuator_proxy import ValveActuatorProxy

class ValvesQueue:
    def __init__(self, hass:HomeAssistant, homematic_duty_cycle_sensor:Union[str, None]):
        self._hass = hass
        self._homematic_duty_cycle_sensor = homematic_duty_cycle_sensor

        self._queue = OrderedDict()
        self._updated_at = utcnow()
        self.update_state()

    def update_state(self):
        self._hass.states.async_set('valves.valves_queue', self.queue_size)

    @property
    def queue_size(self):
        return len(self._queue)

    def set_valve(self, valve_actuator:ValveActuatorProxy, value:int, urgent:bool = True) -> None:
        self._queue[valve_actuator.entity_name] = {
            "valve_actuator": valve_actuator,
            "value": value,
            "urgent": urgent
        }
        self.update_state()
        asyncio.run_coroutine_threadsafe(self.async_process_queue(), self._hass.loop)

    async def async_process_queue(self, now=None) -> None:
        # Get rid of "pylint unused argument warning"
        _ = (now)

        if self.queue_size == 0:
            return
        if utcnow() < self._updated_at + QUEUE_INTERVAL_TIMEDELTA:
            return
        if self.duty_cycle_too_high:
            return
        if self.decalcification_time:
            LOGGER.info("decalcification time")
            return

        self._updated_at = utcnow()
        entry = self._queue.popitem(False)[1]
        valve_actuator = entry["valve_actuator"]
        value = int(entry["value"])
        urgent = bool(entry["urgent"])
        self.update_state()
        try:
            result = await valve_actuator.async_set_valve_position(value, urgent)
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.error(exception)
            result = False
        if result:
            LOGGER.info("%s set to %d via queue. Queue size=%d",
                    valve_actuator.entity_name, value, self.queue_size)
        else:
            LOGGER.warning("Failed to set %s to %d via queue. Rescheduling. Queue size=%d",
                    valve_actuator.entity_name, value, self.queue_size)
            self._queue[valve_actuator.entity_name] = entry

    @property
    def duty_cycle_too_high(self):
        if self._homematic_duty_cycle_sensor is None:
            LOGGER.warning("duty_cycle_too_high: homematic_duty_cycle_sensor missing in config")
            return False
        homematic_duty_cycle_sensor = self._hass.states.get(self._homematic_duty_cycle_sensor)
        if homematic_duty_cycle_sensor is None:
            LOGGER.warning("duty_cycle_too_high: homematic_duty_cycle_sensor does not exist")
            return False
        duty_cycle = homematic_duty_cycle_sensor.state
        if duty_cycle is None:
            LOGGER.warning("duty_cycle_too_high: homematic_duty_cycle_sensor state is missing")
            return False
        too_high = float(duty_cycle) > 75
        if too_high:
            LOGGER.warning("duty cycle too high: %d - don't process queue with keys %s",
                    float(duty_cycle), list(self._queue.keys()))
        return too_high

    @property
    def decalcification_time(self):
        now = datetime.now()
        # decal day is saturday (5)
        if now.weekday() != 5:
            return False
        now_str = now.strftime("%H:%M:%S")
        return now_str >= "10:55:00" and now_str <= "11:05:00"
