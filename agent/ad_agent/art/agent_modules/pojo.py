from typing import Literal
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage


class InterruptInAdAgent(BaseModel):
    type: Literal["interrupt_generate_plan", "interrupt_execute_plan", "tool_call"] = Field(
        description="中断类型，interrupt_generate_plan表示生成计划中断，interrupt_execute_plan表示执行计划中断,tool")
    message_list: list[BaseMessage] = Field(
        description="中断消息，中断消息会作为resume参数传递给agent")
