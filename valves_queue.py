
from datetime import datetime
from collections import OrderedDict

from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from .const import (
    LOGGER,
    QUEUE_INTERVAL_TIMEDELTA
)
from .valve_actuator_proxy import ValveActuatorProxy

class ValvesQueue:
    def __init__(self, hass:HomeAssistant):
        self._hass = hass
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
        self.process_queue()

    def process_queue(self, now=None) -> None:
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
        valve_actuator.set_valve_position(value, urgent)
        LOGGER.info("%s set to %d via queue. Queue size=%d",
                valve_actuator.entity_name, value, self.queue_size)

    @property
    def duty_cycle_too_high(self):
        ccu2 = self._hass.states.get("homematic.ccu2")
        if ccu2 is None:
            LOGGER.warning("duty_cycle_too_high: ccu2 missing")
            return False
        duty_cycle = ccu2.attributes.get("DutyCycle")
        if duty_cycle is None:
            LOGGER.warning("duty_cycle_too_high: DutyCycle missing in ccu2")
            return False
        too_high = int(duty_cycle) > 75
        if too_high:
            LOGGER.warning("duty cycle too high: %d - don't process queue with keys %s",
                    int(duty_cycle), list(self._queue.keys()))
        return too_high

    @property
    def decalcification_time(self):
        now = datetime.now()
        # decal day is saturday (5)
        if now.weekday() != 5:
            return False
        now_str = now.strftime("%H:%M:%S")
        return now_str >= "10:55:00" and now_str <= "11:05:00"
