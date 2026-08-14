"""Validated, serializable MR event graph models."""
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

ChannelName = Literal["rf_amp", "rf_phase", "gx", "gy", "gz", "adc_gate", "nco_freq", "nco_phase"]

class Event(BaseModel):
    time: float = Field(ge=0, description="Seconds from sequence start")
    value: float

class Channel(BaseModel):
    name: ChannelName
    events: list[Event] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self):
        if any(a.time > b.time for a, b in zip(self.events, self.events[1:])):
            raise ValueError("events must be ordered by time")
        return self

class SequenceIR(BaseModel):
    name: str
    duration: float = Field(gt=0)
    channels: list[Channel]
    metadata: dict[str, Any] = Field(default_factory=dict)

    def channel(self, name: ChannelName) -> list[Event]:
        return next((c.events for c in self.channels if c.name == name), [])

class TemplateRequest(BaseModel):
    template: Literal["SE", "TSE", "GRE"]
    params: dict[str, float | int] = Field(default_factory=dict)
