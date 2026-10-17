from pydantic import BaseModel, Field
from typing import Literal

class LoginRequest(BaseModel):
    username: str
    pin: str

class TurnRequest(BaseModel):
    user_id: int
    transcript: str = Field(max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    alternate_transcript: str | None = Field(default=None, max_length=1000)
    session_id: str | None = None

class ConfirmRequest(BaseModel):
    user_id: int
    session_id: str
    confirmed: bool

class LivenessRequest(BaseModel):
    user_id: int
    session_id: str
    token: str
    spoken_phrase: str

class PinRequest(BaseModel):
    user_id: int
    session_id: str
    pin: str = Field(min_length=4, max_length=32)

class AgentAction(BaseModel):
    action: Literal["approve", "reject", "repeat"]
    note: str = Field(min_length=3, max_length=500)

class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
