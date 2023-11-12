from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field
from typing_extensions import Annotated

from marvin import settings


class ResponseFormat(BaseModel):
    type: str


LogitBias = dict[int, float]


class Function(BaseModel):
    name: str
    description: Optional[str]
    parameters: dict[str, Any]


class Tool(BaseModel):
    type: str
    function: Function


class FunctionCall(BaseModel):
    name: str


class BaseMessage(BaseModel):
    content: str
    role: str


class Prompt(BaseModel):
    messages: list[BaseMessage] = Field(default_factory=list)
    tools: Optional[list[Tool]] = None
    tool_choice: Optional[Union[Literal["auto"], dict[str, Any]]] = None
    logit_bias: Optional[LogitBias] = None
    max_tokens: Optional[Annotated[int, Field(strict=True, ge=1)]] = None


class ResponseModel(BaseModel):
    model: type
    name: str = Field(default="FormatResponse")
    description: str = Field(default="Response format")


class ChatRequest(Prompt):
    model: str = Field(default=settings.openai.chat.completions.model)
    frequency_penalty: Optional[
        Annotated[float, Field(strict=True, ge=-2.0, le=2.0)]
    ] = 0
    n: Optional[Annotated[int, Field(strict=True, ge=1)]] = 1
    presence_penalty: Optional[
        Annotated[float, Field(strict=True, ge=-2.0, le=2.0)]
    ] = 0
    response_format: Optional[ResponseFormat] = None
    seed: Optional[int] = None
    stop: Optional[Union[str, list[str]]] = None
    stream: Optional[bool] = False
    temperature: Optional[Annotated[float, Field(strict=True, ge=0, le=2)]] = 1
    top_p: Optional[Annotated[float, Field(strict=True, ge=0, le=1)]] = 1
    user: Optional[str] = None


class AssistantMessage(BaseMessage):
    id: str
    thread_id: str
    created_at: int
    assistant_id: Optional[str] = None
    run_id: Optional[str] = None
    file_ids: list[str] = []
    metadata: dict[str, Any] = {}


class Run(BaseModel):
    id: str
    thread_id: str
    created_at: int
    status: str
    model: str
    instructions: Optional[str]
    tools: Optional[list[Tool]] = None
    metadata: dict[str, str]
