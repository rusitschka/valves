from typing import Any

from .const import (
    DEFAULT_FELT_TEMP_DELTA,
    DEFAULT_SWEET_SPOT
)

class TargetTemperaturConfig:
    def __init__(self):
        self.felt_temp_delta = DEFAULT_FELT_TEMP_DELTA
        self.sweet_spot = DEFAULT_SWEET_SPOT

    def from_json(self, json: dict[str, Any]):
        self.felt_temp_delta = json["felt_temp_delta"]
        self.sweet_spot = json["sweet_spot"]

    def to_json(self) -> dict[str, Any]:
        return {
            "felt_temp_delta": round(self.felt_temp_delta, 2),
            "sweet_spot": round(self.sweet_spot, 1)
        }
