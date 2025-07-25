# 采用plan框架 - execute - 对当前状态进行更新
import json
import re
import inspect
import functools
from typing import Callable


def agent_tool(func: Callable):
    """
    装饰器：自动生成工具提示
    提取方法名与注释，生成工具提示
    """
    @functools.wraps(func)  # 确保使用 functools.wraps 来保留原始函数的元数据
    def wrapper(*args, **kwargs):
        # print("Before function execution")
        result = func(*args, **kwargs)
        # print("After function execution")
        return result
    return wrapper

# 都是基于某个状态进行更新

class PlanAgent:
    def __init__(self):
        pass

    def get_tool_prompt(self) -> str:
        """
        获取所有加了@mv2_modify_tool注解的方法的提示词
        """
        tools = {}

        # 获取所有被@mv2_modify_tool装饰的方法
        for name, method in inspect.getmembers(self):
            if hasattr(method, '__wrapped__'):  # 判断是否被@mv2_modify_tool装饰
                # 获取方法的文档字符串
                doc = method.__doc__
                if doc:
                    # 解析文档字符串
                    parsed_doc = self._parse_docstring(doc)
                    tools[name] = parsed_doc

        # 返回JSON格式的工具说明
        return json.dumps(tools, ensure_ascii=False, indent=4)

    def _parse_docstring(self, doc: str) -> dict:
        """
        解析方法的文档字符串，提取描述和参数信息
        """
        if not doc:
            return {"description": "", "args": {}}

        lines = doc.strip().split('\n')
        description = ""
        args = {}

        # 提取描述（第一行或到Args之前的内容）
        for line in lines:
            line = line.strip()
            if line.startswith('Args:'):
                break
            if line and not line.startswith('Args:'):
                description += line + " "

        description = description.strip()

        # 提取参数信息
        in_args_section = False
        for line in lines:
            line = line.strip()
            if line.startswith('Args:'):
                in_args_section = True
                continue
            if in_args_section and line:
                # 匹配参数格式：param_name(type): description
                match = re.match(r'(\w+)\s*\(([^)]+)\):\s*(.+)', line)
                if match:
                    param_name = match.group(1)
                    param_type = match.group(2)
                    param_desc = match.group(3)
                    args[param_name] = f"{param_desc}({param_type})"
                else:
                    # 匹配没有类型注解的参数：param_name: description
                    match = re.match(r'(\w+):\s*(.+)', line)
                    if match:
                        param_name = match.group(1)
                        param_desc = match.group(2)
                        args[param_name] = param_desc

        return {
            "description": description,
            "args": args
        }

    # 创建片段
    @agent_tool
    async def generate_video_fragments(self, index: int, suggestion: str):
        pass

    # 创建视频
    @agent_tool
    async def generate_video(self, index: int, suggestion: str):
        pass

    # 修改视频
    @agent_tool
    async def modify_video(self, index: int, suggestion: str):
        pass

    # 材料预审
    @agent_tool
    async def pre_review_material(self, index: int, suggestion: str):
        pass
