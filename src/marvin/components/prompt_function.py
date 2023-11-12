import inspect
import re
from functools import partial, wraps
from re import Pattern, compile
from typing import Any, Callable, ClassVar, Optional, ParamSpec, Self, Union
from marvin.serializers import create_tool
import pydantic
from pydantic import create_model

from marvin import settings
from marvin.requests import BaseMessage as Message
from marvin.requests import ChatRequest, Function
from marvin.utilities.asyncio import run_sync
from marvin.utilities.jinja import (
    BaseEnvironment,
    split_text_by_tokens,
)
from marvin.utilities.jinja import Environment as JinjaEnvironment
from marvin.utilities.openai import get_client

P = ParamSpec("P")


class Transcript(pydantic.BaseModel):
    content: str
    roles: list[str] = pydantic.Field(default=["system", "user"])
    environment: ClassVar[BaseEnvironment] = JinjaEnvironment

    @property
    def role_regex(self) -> Pattern[str]:
        return compile("|".join([f"\n\n{role}:" for role in self.roles]))

    def render(self: Self, **kwargs: Any) -> str:
        return self.environment.render(self.content, **kwargs)

    def render_to_messages(
        self: Self,
        **kwargs: Any,
    ) -> list[Message]:
        pairs = split_text_by_tokens(
            text=self.render(**kwargs),
            split_tokens=[f"\n{role}" for role in self.roles],
        )
        return [
            Message(
                role=pair[0].strip(),
                content=pair[1],
            )
            for pair in pairs
        ]


def get_function_call(
    fn: Callable[P, Any],
    name: str = "FormatResponse",
    description: str = "Formats the response.",
    field_name: str = "data",
) -> Function:
    return Function(
        name=name,
        description=fn.__doc__,
        parameters=create_model(
            name,
            **{field_name: (inspect.signature(fn).return_annotation, ...)},  # type: ignore
        ).model_json_schema(),
    )


class PromptFn(pydantic.BaseModel):
    messages: list[Message]
    tools: Optional[list[dict[str, Any]]] = pydantic.Field(default=None)
    tool_choice: Optional[dict[str, Any]] = pydantic.Field(default=None)
    logit_bias: Optional[dict[int, float]] = pydantic.Field(default=None)
    max_tokens: Optional[int] = pydantic.Field(default=None)

    def serialize(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)

    def call(self) -> Any:
        return run_sync(self.acall())

    async def acall(self) -> Any:
        payload = ChatRequest(**self.serialize()).model_dump(exclude_none=True)
        return await get_client().chat.completions.create(**payload)  # type: ignore

    @classmethod
    def as_decorator(
        cls: type[Self],
        fn: Optional[Callable[P, Any]] = None,
        *,
        environment: Optional[BaseEnvironment] = None,
        prompt: Optional[str] = None,
        serialize: bool = True,
        response_model_name: str = "FormatResponse",
        response_model_description: str = "Formats the response.",
        response_model_field_name: str = "data",
    ) -> Union[
        Callable[[Callable[P, None]], Callable[P, None]],
        Callable[[Callable[P, None]], Callable[P, Union[dict[str, Any], Self]]],
        Callable[P, Union[dict[str, Any], Self]],
    ]:
        def wrapper(
            fn: Callable[P, Any], *args: P.args, **kwargs: P.kwargs
        ) -> Union[dict[str, Any], Self]:
            tool = create_tool(
                _type=inspect.signature(fn).return_annotation,
                name=response_model_name,
                description=response_model_description,
                field_name=response_model_field_name,
            )

            signature = inspect.signature(fn)
            params = signature.bind(*args, **kwargs)
            params.apply_defaults()

            promptfn = cls(
                messages=Transcript(
                    content=prompt or fn.__doc__ or ""
                ).render_to_messages(
                    **params.arguments,
                    _arguments=params.arguments,
                    _source_code=(
                        "\ndef" + "def".join(re.split("def", inspect.getsource(fn))[1:])
                    ),
                ),
                tool_choice={
                    "type": "function",
                    "function": {"name": tool.function.name},
                },
                tools=[tool.model_dump()],
            )
            if serialize:
                return promptfn.serialize()
            return promptfn

        if fn is not None:
            return wraps(fn)(partial(wrapper, fn))

        def decorator(
            fn: Callable[P, None]
        ) -> Callable[P, Union[dict[str, Any], Self]]:
            return wraps(fn)(partial(wrapper, fn))

        return decorator


prompt_fn = PromptFn.as_decorator
