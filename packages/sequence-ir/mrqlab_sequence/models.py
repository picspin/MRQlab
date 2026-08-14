"""Validated, serializable MR event graph models."""
from typing import Any, Literal
from pydantic import BaseModel, Field, FiniteFloat, field_validator, model_validator

ChannelName = Literal["rf_amp", "rf_phase", "gx", "gy", "gz", "adc_gate", "nco_freq", "nco_phase"]

class Event(BaseModel):
    time: FiniteFloat = Field(ge=0, description="Seconds from sequence start")
    value: FiniteFloat

    @field_validator("time", "value", mode="before")
    @classmethod
    def numeric_not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("event numeric fields must not be boolean")
        return value

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
    duration: FiniteFloat = Field(gt=0)
    channels: list[Channel]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("duration", mode="before")
    @classmethod
    def duration_not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("duration must not be boolean")
        return value

    @model_validator(mode="after")
    def events_within_duration(self):
        if any(
            event.time > self.duration
            for channel in self.channels
            for event in channel.events
        ):
            raise ValueError("all channel events must lie within sequence duration")
        return self

    def channel(self, name: ChannelName) -> list[Event]:
        return next((c.events for c in self.channels if c.name == name), [])

class TemplateRequest(BaseModel):
    template: Literal["SE", "TSE", "GRE"]
    params: dict[str, Any] = Field(default_factory=dict)
