import math
import random

from datetime import timedelta
from typing import Any, Dict

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_SET_POSITION,
    DEVICE_CLASS_DAMPER,
    CoverEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle, utcnow
from homeassistant.util.dt import as_local

from .const import (
    DEFAULT_FELT_TEMP_DELTA,
    DEFAULT_POSITION,
    DEFAULT_SWEET_SPOT,
    LOGGER,
    UPDATE_INTERVAL_TIMEDELTA,
    QUEUE_INTERVAL_TIMEDELTA
)
from .temperature_history import TemperatureHistory
from .temperature_sensor import TemperatureSensor
from .valve_actuator_proxy import ValveActuatorProxy
from .valves_queue import ValvesQueue

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    valves_queue = ValvesQueue(hass)
    async_track_time_interval(hass, valves_queue.process_queue, QUEUE_INTERVAL_TIMEDELTA)

    LOGGER.info("config=%s", config)
    LOGGER.info("discovery_info=%s", discovery_info)
    entities = []
    for valve_entity in discovery_info['entities']:
        entities.append(ValveCover(hass, valves_queue, valve_entity))
    async_add_entities(entities)


class ValveCover(CoverEntity, RestoreEntity):

    def __init__(self, home_assistant:HomeAssistant, valves_queue:ValvesQueue, valve_entity:dict):
        self._home_assistant = home_assistant
        self._valves_queue = valves_queue
        self._name = valve_entity["id"]

        self._position = 0
        # Kp=1.5 was ok without sweet_spot multiply, try 1.5/15 = 0.1
        # 0.1 was ok, but a bit too high
        self._position_factor = float(valve_entity.get("position_factor", 0.07)) # Kp
        self._update_interval = 15 * 60.0 + random.randint(-60, 60) # randomly splay 2 minutes

        self._thermostat_sensor_id = valve_entity["thermostat_sensor"]
        self._peer_id = valve_entity.get("peer_id", None)
        self._settemp_input = valve_entity.get("settemp_input", None)
        self._window_sensor_id = valve_entity.get("window_sensor", None)
        self._min_position = valve_entity.get("min_position", 0)
        self._max_position = valve_entity.get("max_position", 80)
        self._thermostat_inertia = float(valve_entity.get("thermostat_inertia", 60))
        self._valve_inertia = float(valve_entity.get("valve_inertia", 60))
        self._raw_position = -1
        self._raw_position_changed_at = utcnow()
        self._target_temperature = -1.0
        self._target_temperature_changed = False
        self._felt_temp = -1.0
        self._felt_temp_delta = 0.0
        self._real_error = -1.0
        self._error = -1.0
        self._error_exp = -1.0
        self._thermostat_history = TemperatureHistory(timedelta(minutes=60))
        self._valve_history = TemperatureHistory(timedelta(minutes=10))
        self._next_temp_adjust_at = utcnow()
        self._last_valve_adjust_at = utcnow() - timedelta(seconds=self._update_interval / 2)
        self._last_target_temperature_changed_at = utcnow() - timedelta(hours=2)
        self._window_open_until = None
        self._window_open_saved_position = -1.0
        self._valve_position_before_boost_mode = -1.0
        self._sweet_spot = 10.0
        self._sweet_spot_blocked_until = utcnow()
        self._reset_boost_mode_at = utcnow() - timedelta(hours=1)
        self._temperature_sensor = None
        self._valve_actuator = None
        self._updated = False

    async def async_added_to_hass(self) -> None:
        last_state = await self.async_get_last_state()
        if last_state and 'felt_temp_delta' in last_state.attributes:
            self._felt_temp_delta = last_state.attributes['felt_temp_delta']
            LOGGER.info("%s: Restored felt_temp_delta to %.3f", self._name, self._felt_temp_delta)
        else:
            self._felt_temp_delta = DEFAULT_FELT_TEMP_DELTA

        if last_state and 'position' in last_state.attributes:
            self._position = last_state.attributes['position']
            LOGGER.info("%s: Restored position to %.3f", self._name, self._position)
        else:
            self._position = DEFAULT_POSITION

        if last_state and 'sweet_spot' in last_state.attributes:
            self._sweet_spot = last_state.attributes['sweet_spot']
            LOGGER.info("%s: Restored sweet_spot to %.3f", self._name, self._sweet_spot)
        else:
            self._sweet_spot = DEFAULT_SWEET_SPOT

        self._raw_position = math.ceil(self._position)
        self._temperature_sensor = TemperatureSensor(
                self._home_assistant, self._thermostat_sensor_id)
        self._valve_actuator = ValveActuatorProxy(
                self._home_assistant, self._name)

        await super().async_added_to_hass()


    @property
    def supported_features(self):
        return SUPPORT_SET_POSITION

    @property
    def unique_id(self) -> str:
        return self.entity_id_to_cover_id(self._name)

    def entity_id_to_cover_id(self, entity_id):
        return self.platform.domain + "." + entity_id.replace(".", "_")

    @property
    def device_class(self):
        return DEVICE_CLASS_DAMPER

    @property
    def name(self) -> str:
        return self.platform.domain + "." + self._name.replace(".", "_")

    @property
    def current_cover_position(self):
        return None if self._position < 0 else self._position

    def set_cover_position(self, **kwargs):
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self.queue_set_valve(position)

    @property
    def state(self) -> int:
        return self.current_cover_position

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        if not self._updated:
            return {}

        attributes = {
            "position": round(self._position, 2),
            "raw_position": round(self._raw_position, 2),
            "felt_temp": round(self._felt_temp, 3),
            "felt_temp_delta": round(self._felt_temp_delta, 3),
            "error": round(self._error, 3),
            "error_exp": round(self._error_exp, 3),
            "real_error": self._real_error,
            "sweet_spot": round(self._sweet_spot, 3),
            "thermostat_slope": round(self._thermostat_history.slope, 3),
            "valve_slope": round(self._valve_history.slope, 3),
            "next_temp_adjust_at": as_local(self._next_temp_adjust_at).strftime("%H:%M:%S")
        }
        return attributes

    @Throttle(UPDATE_INTERVAL_TIMEDELTA)
    def update(self) -> None:
        if (not self._valve_actuator.available or
                not self._temperature_sensor.available):
            return

        self.normalize_devices_state()

        #LOGGER.info("%s", self._valve_temperature_sensor.entity)
        raw_position = self._valve_actuator.valve_position
        if raw_position is None:
            LOGGER.info("%s: Position not available", self._name)
            return

        if raw_position == self._raw_position:
            if (abs(raw_position - math.ceil(self._position) > 10)
                    and utcnow() > self._raw_position_changed_at + timedelta(minutes=45)):
                LOGGER.info("%s: Position changed to %d because it differs too much from %d",
                        self._name, raw_position, self._position)
                self._position = raw_position
        else:
            if raw_position == math.ceil(self._position):
                LOGGER.info("%s: Position changed from %d to %d",
                        self._name, self._raw_position, raw_position)
            else:
                LOGGER.info("%s: Position changed by third party from %d to %d",
                        self._name, self._raw_position, raw_position)
                self._position = raw_position
            self._raw_position = raw_position
            self._raw_position_changed_at = utcnow()

        self.update_target_temperature()

        # eurotronic has bug - try to work-around
        if self._valve_actuator.value < 5.0:
            LOGGER.info("%s skipping update: Has strange temp %f",
                    self._name, self._valve_actuator.value)
            return

        self._thermostat_history.add_value(self._temperature_sensor.value)
        self._valve_history.add_value(self._valve_actuator.value)

        felt_ratio = 0.667
        self._felt_temp = (
            self._temperature_sensor.value * felt_ratio
            + self._valve_actuator.value * (1.0 - felt_ratio))
        #average_felt_temp = self._felt_temp
        adjusted_felt_temp_delta = self._felt_temp_delta
        peer_entity = self.peer_entity
        # if peer_entity is not None:
        #     peer_felt_temp = peer_entity.attributes.get("felt_temp")
        #     if peer_felt_temp is not None:
        #         average_felt_temp = 0.5 * (average_felt_temp + float(peer_felt_temp))
        #         #LOGGER.info("%s: Average felt temp: %.3f", self._name, average_felt_temp)
        if peer_entity is not None:
            peer_felt_temp_delta = peer_entity.attributes.get("felt_temp_delta")
            if peer_felt_temp_delta is not None:
                diff = self._felt_temp_delta - float(peer_felt_temp_delta)
                # "+=" would be wrong here - tested with Wohnzimmer valves where
                # the colder turned off earlier
                # weight with only 0.25 instead of 0.5 (=average)
                adjusted_felt_temp_delta -= 0.25 * diff
                #LOGGER.info("%s: Adjusted felt temp delta from %.3f to %.3f",
                #       self._name, self._felt_temp_delta, adjusted_felt_temp_delta)

        # kd with felt_ratio of 0.5: 0.5 overshoots, 1.0 turns off too early
        # kd with felt_ratio of 0.667: try 0.5
        self._real_error = round(self._temperature_sensor.value - self._target_temperature, 3)
        self._error = (
            self._felt_temp
            + self._thermostat_history.slope * 0.5 # kd
            - self._target_temperature
            - adjusted_felt_temp_delta)
        # make delta exponential, see https://www.wolframalpha.com/input/
        # and https://www.desmos.com/calculator
        # 0.1=>0.1, 0.5=>1.0 => a=0.84, b=1.73
        # a*0.1*e^(b*0.1)=0.1,a*0.3*e^(b*0.3)=0.6 => a=0.71, b=3.47
        self._error_exp = 0.71 * self._error * math.exp(3.47 * abs(self._error))

        self._updated = True

        if self.update_boost_mode():
            return

        if self.update_window_open():
            return

        self._next_temp_adjust_at = (
                self._last_valve_adjust_at +
                timedelta(seconds=self._update_interval))
        if utcnow() >= self._next_temp_adjust_at:
            self._last_valve_adjust_at = utcnow()
            self.adjust_position()

    def normalize_devices_state(self):
        #LOGGER.info("temp sensor %s", repr(self._thermostat_temperature_sensor.entity.device_info))
        #LOGGER.info("valve %s", repr(self._valve_temperature_sensor.entity.device_info))
        if self._temperature_sensor.entity_attribute("mode") != "Boost":
            res = self._valve_actuator.normalize_valve_state()
            res = res or self._temperature_sensor.normalize_thermostat_state()
            if res:
                self.queue_set_valve(math.ceil(self._sweet_spot), False)

    @property
    def peer_entity(self):
        if self._peer_id is None:
            return None
        else:
            return self._home_assistant.states.get(self.entity_id_to_cover_id(self._peer_id))

    @property
    def window_entity(self):
        if self._window_sensor_id is None:
            return None
        else:
            return self._home_assistant.states.get(self._window_sensor_id)

    def update_target_temperature(self) -> None:
        if self._settemp_input is not None:
            target_temperature = float(self._home_assistant.states.get(self._settemp_input).state)
        else:
            target_temperature = self._temperature_sensor.entity_attribute("temperature")
        temperature_adjust_sensor = self._home_assistant.states.get("sensor.temperature_adjust")
        if temperature_adjust_sensor:
            target_temperature = target_temperature + float(temperature_adjust_sensor.state)
        if (self._target_temperature >= 0 and
                abs(self._target_temperature - target_temperature) >= 0.5):
            self._last_valve_adjust_at = utcnow() - timedelta(seconds=self._update_interval)
            self._last_target_temperature_changed_at = utcnow()
            self._target_temperature_changed = True
        if self._target_temperature != target_temperature:
            self._target_temperature = target_temperature


    def adjust_position(self) -> None:
        # use raw_position instead of position for learning because,
        # e.g. for eurotronic they may differ alot.
        # update only when last valve change was more than 4 hours ago
        if (self._raw_position > 0
                and utcnow() >= self._last_target_temperature_changed_at + timedelta(hours=4)):
            combined_fitness = max(
                    0.5,
                    1.0 - abs(self._thermostat_history.slope) - abs(self._real_error))
            learn_weight = 0.00003 * self._update_interval * combined_fitness

            sweet_spot_learn_weight = learn_weight
            self._sweet_spot = (
               self._sweet_spot * (1.0 - sweet_spot_learn_weight)
               + float(self._raw_position) * sweet_spot_learn_weight)
            # sweet_spot_learn_weight = 0.000005 * self._update_interval
            # if self._sweet_spot < self._raw_position:
            #     self._sweet_spot = min(40.0, self._sweet_spot * sweet_spot_learn_weight)
            # else:
            #     self._sweet_spot = max(1.0, self._sweet_spot / sweet_spot_learn_weight)

            felt_temp_delta = self._felt_temp - self._temperature_sensor.value
            # felt_temp_delta < 0 will decrease ratio, 0 is 1, > 0 will incrase ratio
            felt_temp_learn_weight = learn_weight * math.exp(felt_temp_delta)
            #felt_temp_learn_weight = learn_weight
            #felt_temp_learn_weight = felt_temp_learn_weight * 100.0 # only temporary: learn faster!
            self._felt_temp_delta = (
                self._felt_temp_delta * (1.0 - felt_temp_learn_weight)
                + felt_temp_delta * felt_temp_learn_weight)

            LOGGER.info((
                    "%s: New learn: real_error=%.3f, slope=%.3f, felt_temp_delta=%.3f"
                    ", learn_weight=%.3f, sweet_spot_learn_weight=%.3f"
                    ", felt_temp_learn_weight=%.3f"),
                self._name,
                self._real_error,
                self._thermostat_history.slope,
                felt_temp_delta,
                learn_weight,
                sweet_spot_learn_weight,
                felt_temp_learn_weight)

        average_sweet_spot = self._sweet_spot
        # peer_entity = self.peer_entity
        # if peer_entity is not None:
        #     peer_sweet_spot = peer_entity.attributes.get("sweet_spot")
        #     if peer_sweet_spot is not None:
        #         average_sweet_spot = 0.5 * (average_sweet_spot + float(peer_sweet_spot))
        #         LOGGER.info("%s: Average sweet spot: %.3f", self._name, average_sweet_spot)

        valve_pos = self._position
        if self._target_temperature_changed:
            self._target_temperature_changed = False
            new_valve_pos = valve_pos - 2.0 * self._error * self._sweet_spot
        else:
            #valve_delta = float(-self._error_exp * self._position_factor * self._sweet_spot)
            valve_delta = float(-self._error_exp * self._position_factor * average_sweet_spot)
            # put valve delta on a logarithmic scale: valve_pos 0=>1, 20=>2
            #valve_delta = valve_delta * math.exp(math.log(2) * valve_pos / 20.0)
            new_valve_pos = valve_pos + valve_delta

        adaptive_max_position = max(10.0, min(self._max_position, self._sweet_spot * 2.0))
        new_valve_pos = min(adaptive_max_position, max(self._min_position, new_valve_pos))
        # if coming from position 0 directly jump to ratio of sweet spot depending on slope
        if self._position == 0 and new_valve_pos > 0 and self._thermostat_history.slope < 0:
            # slope factor 1.0 was a too agressive (esp. during night)
            slope_factor = 0.75
            new_valve_pos = max(
                    new_valve_pos,
                    self._sweet_spot * slope_factor * -self._thermostat_history.slope)
        valve_pos_changes = math.ceil(new_valve_pos) != self._raw_position

        self._position = new_valve_pos
        if valve_pos_changes:
            self.queue_set_valve(math.ceil(new_valve_pos), False)
            LOGGER.info((
                        "%s: queued: "
                        "  current_temperature=%.2f  target_temperature=%.2f  "
                        "  error=%.2f  valve_pos=%.2f  new_valve_pos=%.2f"
                    ),
                    self.name,
                    self._temperature_sensor.value,
                    self._target_temperature,
                    self._error,
                    valve_pos,
                    new_valve_pos)


    def queue_set_valve(self, valve_pos:int, urgent:bool = True) -> None:
        self._valves_queue.set_valve(self._valve_actuator, valve_pos, urgent)

    def update_window_open(self) -> bool:
        window_entity = self.window_entity
        window_entity_is_longer_open = (
            window_entity is not None
            and window_entity.state == "on"
            and utcnow() - window_entity.last_changed >= timedelta(minutes=2))
        #LOGGER.info("%s: window_entity_is_longer_open = %r",
        #       self.name, window_entity_is_longer_open)
        #if window_entity_is_longer_open:
        if self._valve_history.slope < -10.0 or window_entity_is_longer_open:
            self._window_open_until = utcnow() + timedelta(minutes=10)
            self._sweet_spot_blocked_until = utcnow() + timedelta(hours=2)
            if self._window_open_saved_position < 0:
                LOGGER.info("%s: slope %.2f too low or window switch open. Window open triggered.",
                        self.name, self._valve_history.slope)
                self._window_open_saved_position = self._position
                self.queue_set_valve(0)
            return True

        if self._window_open_saved_position < 0:
            return False

        if utcnow() > self._window_open_until:
            LOGGER.info("%s: Reset window open and set valve back to position %d",
                    self.name, self._window_open_saved_position)
            self.queue_set_valve(self._window_open_saved_position)
            self._thermostat_history.reset()
            self._window_open_until = None
            self._window_open_saved_position = -1
            self._last_valve_adjust_at = utcnow()

        return True

    def update_boost_mode(self) -> bool:
        is_boost_mode = self._temperature_sensor.entity_attribute("mode") == "Boost"
        if self._valve_position_before_boost_mode < 0 and is_boost_mode:
            LOGGER.info("%s: Starting boost mode", self.name)
            self._valve_position_before_boost_mode = self._position
            self.queue_set_valve(80)
            return True
        if self._valve_position_before_boost_mode >= 0 and not is_boost_mode:
            if self._position == self._valve_position_before_boost_mode:
                LOGGER.info("%s: Boost mode ended", self.name)
                self._valve_position_before_boost_mode = -1
            else:
                self.reset_boost_mode()
            return True
        return is_boost_mode

    def reset_boost_mode(self) -> None:
        if utcnow() > self._reset_boost_mode_at + timedelta(minutes=5):
            LOGGER.info("%s: Resetting boost mode", self.name)
            self._reset_boost_mode_at = utcnow()
            self.queue_set_valve(self._valve_position_before_boost_mode)
