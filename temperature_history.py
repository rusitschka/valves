from collections import deque
from datetime import timedelta

from homeassistant.util import utcnow

class TemperatureHistory:
    class Item:
        value = 0.0
        timestamp = None

    def __init__(self, history_timedelta:timedelta):
        self._history_timedelta = history_timedelta
        self._history = deque()

        now = utcnow()
        self._value = 0.0
        self._updated_at = now
        self._last_value = 0.0
        self._last_updated_at = now
        self._average_value = 0.0

    @property
    def average_value(self):
        return self._average_value


    def add_value(self, value):
        now = utcnow()
        expire_at = now - self._history_timedelta
        while len(self._history) > 0 and self._history[0].timestamp < expire_at:
            #LOGGER.info("delete with ts=%s because of e=%s", self._history[0].timestamp, expire_at)
            self._history.popleft()

        self._value = value
        self._updated_at = now

        item = TemperatureHistory.Item()
        item.value = value
        item.timestamp = now
        self._history.append(item)

        if len(self._history) == 1:
            self._last_value = value
            self._last_updated_at = now - self._history_timedelta
            self._average_value = value
        else:
            total = 0.0
            for item in self._history:
                total = total + item.value
            self._average_value = total / len(self._history)

            last_item = self._history[0]
            self._last_value = last_item.value
            self._last_updated_at = last_item.timestamp

        #LOGGER.info("history size %d for delta %s", len(self._history), self._history_timedelta)

    @property
    def slope(self) -> float:
        last_update_age_in_seconds = (utcnow() - self._last_updated_at).total_seconds()
        # If there was no update for one hour, set slope to 0
        if last_update_age_in_seconds > 3600:
            return 0
        else:
            return (self._value - self._last_value) * 3600.0 / self._history_timedelta.total_seconds()

    def reset(self) -> None:
        self._history.clear()
        self.add_value(self._value)
