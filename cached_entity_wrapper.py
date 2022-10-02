
from typing import Union

from homeassistant.core import HomeAssistant

from .const import LOGGER

class CachedEntityWrapper:
    def __init__(self, home_assistant:HomeAssistant, entity_name:str):
        self._home_assistant = home_assistant
        self._entity_name = entity_name
        self._cached_entity_attributes = {}
        LOGGER.info("%s/%s: CachedEntityWrapper initialized",
                self.__class__.__name__, self._entity_name)

    @property
    def entity_name(self):
        return self._entity_name

    @property
    def entity(self):
        return self._home_assistant.states.get(self._entity_name)

    @property
    def value(self) -> Union[float, None]:
        raise NotImplementedError()

    def entity_attribute(self, attribute_name:str):
        if self.entity is not None:
            value = self.entity.attributes.get(attribute_name)
        else:
            #LOGGER.info("%s is unavailable. Set value of %s to None"
            #       % (self._entity_name, attribute_name))
            value = None
        if value is None:
            value = self._cached_entity_attributes.get(attribute_name, None)
            if value is not None:
                LOGGER.info("%s: value is None - using cached value for %s",
                        self._entity_name, attribute_name)
        else:
            self._cached_entity_attributes[attribute_name] = value
        return value

    @property
    def available(self) -> bool:
        return self.entity is not None and self.value is not None
