from datetime import timedelta
import logging

DEFAULT_FELT_TEMP_DELTA = 0.0
DEFAULT_POSITION = -1.0
DEFAULT_SWEET_SPOT = 10.0

DOMAIN = 'valves'

LOGGER = logging.getLogger(__package__)

UPDATE_INTERVAL = 30
UPDATE_INTERVAL_TIMEDELTA = timedelta(seconds=UPDATE_INTERVAL)

QUEUE_INTERVAL_TIMEDELTA = timedelta(seconds=10)
