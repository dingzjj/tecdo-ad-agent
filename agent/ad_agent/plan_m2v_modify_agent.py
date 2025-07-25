
from agent.utils import get_video_duration
from agent.llm import get_gemini_multimodal_model
from agent.ad_agent.prompt import EXTRACT_GENERATE_VIDEO_INFORMATION_SYSTEM_PROMPT_cn, EXTRACT_GENERATE_VIDEO_INFORMATION_RESPONSE_SCHEMA, EXTRACT_GENERATE_VIDEO_INFORMATION_SYSTEM_PROMPT_cn, EXTRACT_GENERATE_VIDEO_INFORMATION_RESPONSE_SCHEMA
from langchain_core.messages import BaseMessage
import os
from agent.utils import get_url_data
from agent.ad_agent.prompt import EXTRACT_GENERATE_FRAGMENT_INFORMATION_SYSTEM_PROMPT_cn, EXTRACT_GENERATE_FRAGMENT_INFORMATION_RESPONSE_SCHEMA
from agent.ad_agent.prompt import REGENERATE_UPDATE_OPERATIONS_SYSTEM_PROMPT_cn, REGENERATE_UPDATE_OPERATIONS_HUMAN_PROMPT_cn
import asyncio
from agent.ad_agent.m2v_workflow import GenerateVideoState
from agent.ad_agent.exception import HumanError, AIError
from agent.third_part.i2v import i2v_strategy_chain
import inspect
from typing import Callable
import functools
import json
import re
from agent.llm import AzureChatOpenAIClient
from config import logger
from json import JSONDecodeError
from typing_extensions import Dict
from agent.ad_agent.prompt import GENERATE_UPDATE_OPERATIONS_SYSTEM_PROMPT_cn, GENERATE_UPDATE_OPERATIONS_HUMAN_PROMPT_cn, GENERATE_UPDATE_OPERATIONS_SYSTEM_PROMPT_en, GENERATE_UPDATE_OPERATIONS_HUMAN_PROMPT_en
from agent.ad_agent.prompt import REGENERATE_UPDATE_OPERATIONS_SYSTEM_PROMPT_en, REGENERATE_UPDATE_OPERATIONS_HUMAN_PROMPT_en
from agent.mini_agent import AnalyseImageAgent
from agent.ad_agent.m2v_workflow import VideoFragment
from config import conf
from agent.ad_agent.m2v_workflow import get_m2v_workflow
import uuid
from langchain_core.runnables import RunnableConfig
from agent.utils import create_dir
from langchain_core.messages import HumanMessage, AIMessage
app = get_m2v_workflow()


def mv2_modify_tool(func: Callable):
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


class M2VAgent:
    # M2VWorkflowTool是M2VAgent的工具箱
    def __init__(self):
        self.MAX_RETRY_TIME = 3
        self.workflow_state = None

    # 将需要操作的workflow_state设置到M2VAgent中
    def set_workflow_state(self, workflow_state: GenerateVideoState):
        self.workflow_state = workflow_state
        return self

    def get_workflow_state(self) -> GenerateVideoState:
        if self.workflow_state is None:
            raise Exception("workflow_state is not set")
        return self.workflow_state

    async def extract_generate_video_information(self, chat_history: list[BaseMessage], overhead_information: dict):
        """
        从聊天历史中提取商品名称、商品信息、模特图片、视频片段时长，没有则使用默认值
        """
        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=EXTRACT_GENERATE_VIDEO_INFORMATION_SYSTEM_PROMPT_cn,
            response_schema=EXTRACT_GENERATE_VIDEO_INFORMATION_RESPONSE_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                message.content for message in chat_history
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        product = content["product"]
        product_info = content["product_info"]
        if content["video_fragment_duration"] != 0:
            self.workflow_state.video_fragment_duration = content["video_fragment_duration"]
        if content["product"] != "":
            self.workflow_state.product = product
        else:
            self.workflow_state.product = "clothes"
        if content["product_info"] != "":
            self.workflow_state.product_info = product_info
        else:
            self.workflow_state.product_info = "clothes"
        if content["prompt"] != "":
            self.workflow_state.video_positive_prompt = content["prompt"]
        if content["negative_prompt"] != "":
            self.workflow_state.video_negative_prompt = content["negative_prompt"]
        self.workflow_state.model_images = [
            value for key, value in overhead_information.items() if key.startswith("img_")]
        return {"workflow_state": self.workflow_state}

    async def extract_generate_fragment_information(self, chat_history: list[BaseMessage]) -> dict:
        """
        从聊天历史中提取商品名称、商品信息、提示词，负面提示词，片段中人物的动作，视频时长，生成视频片段，一定要显式提供，不能推断出来，没有则使用默认值
        """
        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=EXTRACT_GENERATE_FRAGMENT_INFORMATION_SYSTEM_PROMPT_cn,
            response_schema=EXTRACT_GENERATE_FRAGMENT_INFORMATION_RESPONSE_SCHEMA)
        response = gemini_generative_model.generate_content(
            [
                message.content for message in chat_history
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        if content["product"] == "":
            content["product"] = "clothes"
        if content["product_info"] == "":
            content["product_info"] = "clothes"
        if content["video_fragment_duration"] == 0:
            content["video_fragment_duration"] = 5.0
        if content["i2v_strategy"] == "":
            content["i2v_strategy"] = "keling"
        return content

    async def regenerate_update_operations(self, suggestion: str, error_info: str, old_update_operations: list[dict]) -> list[dict]:
        """
        根据错误信息重新生成更新操作,重新生成update_operations操作
        """
        # 1.获取工具提示
        tool_prompt = self.get_tool_prompt()
        retry_time = 0
        # 2.设置提示词
        system_prompt = REGENERATE_UPDATE_OPERATIONS_SYSTEM_PROMPT_en.format(
            tool_prompt=tool_prompt)
        human_prompt = REGENERATE_UPDATE_OPERATIONS_HUMAN_PROMPT_en.format(
            suggestion=suggestion, error_info=error_info, update_operations=old_update_operations)
        client = AzureChatOpenAIClient()
        while retry_time < self.MAX_RETRY_TIME:
            # 3.调用模型
            response = client.chat_with_history(system_prompt, human_prompt)
            try:
                update_operations: dict = json.loads(response)
                if "update_operations" in update_operations:
                    new_update_operations = update_operations["update_operations"]
                    for update_operation in new_update_operations:
                        update_operation["status"] = "pending_execution"
                    # 将当前的update_operations与append_update_operations合并
                    return new_update_operations
                else:
                    raise HumanError(update_operations["error_info"])
            except JSONDecodeError as e:
                logger.error(f"生成更新操作失败: {e}")
                error_info = f"json解析失败: {e}"
                human_prompt = f"{human_prompt},并且错误信息: {error_info}"
                retry_time += 1
        raise Exception("生成更新操作失败")

    async def generate_update_operations(self, chat_history: list[BaseMessage]) -> list[dict]:
        """
        生成更新操作
        chat_history: 聊天历史,用于记录用户与agent的对话
        """
        assert isinstance(chat_history[-1], HumanMessage)
        # 1.获取工具提示
        tool_prompt = self.get_tool_prompt()
        retry_time = 0
        # 2.设置提示词
        system_prompt = GENERATE_UPDATE_OPERATIONS_SYSTEM_PROMPT_cn.format(
            tool_prompt=tool_prompt)
        client = AzureChatOpenAIClient()
        while retry_time < self.MAX_RETRY_TIME:
            # 3.调用模型
            response = client.chat_with_history(system_prompt, chat_history)
            # load出现异常的话反馈给llm，让llm进行修正
            try:
                update_operations = json.loads(response)
                if "update_operations" in update_operations:
                    update_operations = update_operations["update_operations"]
                    for update_operation in update_operations:
                        update_operation["status"] = "pending_execution"
                    return update_operations
                else:
                    client.set_callback(
                        f"""{chat_history[-1].content},并且错误信息:json解析失败：缺少update_operations""")
                    retry_time += 1

            except JSONDecodeError as e:
                logger.error(f"生成更新操作失败: {e}")
                client.set_callback(
                    f"""{chat_history[-1].content},并且错误信息:json解析失败：缺少update_operations""")
                retry_time += 1
        raise Exception("生成更新操作失败")

    async def invoke(self,  update_operations: list[Dict]) -> GenerateVideoState:
        """
        调用m2v_agent
        """
        # 在调用时发生错误的话，则将错误反馈给用户，让用户进行补充
        for update_operation in update_operations:
            tool_name = update_operation["tool_name"]
            parameters = update_operation["parameters"]
            # 获取参数列表，转换为字典形式
            parameters = {param["parameter_name"]: param["parameter_value"]
                          for param in update_operation["parameters"]}
            # 使用 getattr 动态调用方法，并传递解包的参数
            method = getattr(self, tool_name, None)
            try:
                if method:
                    await method(**parameters)  # 动态调用方法并传递参数
                    update_operation["status"] = "success"
                else:
                    raise AIError(f"未找到方法: {tool_name}")
            except AIError as e:
                # 根据异常让llm进行修正
                raise e
            except HumanError as e:
                # 调用失败时返回错误信息，用户收到错误信息后需要重新提供建议
                update_operation["status"] = "failed"
                raise e
        return self.workflow_state

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

    # 1.结合用户建议重新生成视频片段

    @mv2_modify_tool
    async def re_generate_video_fragments(self, index: int, suggestion: str):
        """
        重新生成视频片段,index是从1开始的
        Args:
            index(int): 视频片段索引
            suggestion(str): 用户建议
        """
        workflow_state = self.workflow_state
        now_video_fragment = None

        # 进行校验
        # 获取index对应的片段信息
        for video_fragment in workflow_state.video_fragments:
            if video_fragment.video_index == index:
                now_video_fragment = video_fragment
                break
        if now_video_fragment is None:
            raise HumanError(f"视频片段索引{index}不存在")

        video_positive_prompt, video_negative_prompt, video_url = asyncio.run(i2v_strategy_chain.execute_chain_with_suggestion(
            product=workflow_state.product,
            product_info=workflow_state.product_info,
            img_path=now_video_fragment.model_image,
            img_info=now_video_fragment.model_image_info,
            duration=workflow_state.video_fragment_duration,
            resolution={},
            video_type=now_video_fragment.video_type,
            i2v_strategy=workflow_state.i2v_strategy,
            suggestion=suggestion))
        # 对state进行更新
        now_video_fragment.video_positive_prompt = video_positive_prompt
        now_video_fragment.video_negative_prompt = video_negative_prompt
        now_video_fragment.video_url_v1 = video_url

    # 2.变换转场特效
    @mv2_modify_tool
    async def change_transition_effect(self, begin, end, transition_effect):
        """
        变换开始索引与结束索引对应的视频之间转场特效,index是从1开始的
        Args:
            begin(int): 开始索引
            end(int): 结束索引
            transition_effect: 转场特效
        """
        workflow_state = self.workflow_state
        # 进行校验
        # 获取begin和end对应的片段信息
        for video_fragment in workflow_state.video_fragments:
            if video_fragment.video_index == begin:
                begin_video_fragment = video_fragment
            if video_fragment.video_index == end:
                end_video_fragment = video_fragment
        if begin_video_fragment is None or end_video_fragment is None:
            raise HumanError(f"开始索引{begin}或结束索引{end}对应的视频片段不存在")
        # 进行更新
        workflow_state.output_video.transition_effect[begin -
                                                      1] = transition_effect

    # 3.调换片段顺序
    @mv2_modify_tool
    async def change_video_fragment_order(self, from_index, to_index):
        """
        调换片段顺序,index是从1开始的
        Args:
            from_index(int): 开始索引
            to_index(int): 结束索引
        """
        workflow_state = self.workflow_state
        from_video_fragment = None
        to_video_fragment = None

        # from_index和to_index变成Int
        from_index = int(from_index)
        to_index = int(to_index)
        # 进行校验
        # 获取from_index和to_index对应的片段信息
        for video_fragment in workflow_state.video_fragments:
            if video_fragment.video_index == from_index:
                from_video_fragment = video_fragment
            if video_fragment.video_index == to_index:
                to_video_fragment = video_fragment
        if from_video_fragment is None or to_video_fragment is None:
            raise HumanError(
                f"开始索引{from_index}或结束索引{to_index}对应的视频片段不存在")
        # 进行更新
        from_video_fragment.video_index = to_index
        to_video_fragment.video_index = from_index

    # @mv2_modify_tool
    # async def invoke_m2v_workflow(self, product: str, product_info: str, model_images: list, video_fragment_duration: int):
    #     """
    #     调用m2v_workflow工作流,根据模特图片生成视频片段
    #     """
    #     video_output_path = conf.get_path("m2v_workflow_result_dir")
    #     id = str(uuid.uuid4())
    #     with create_dir(video_output_path, name=id) as temp_dir_path:
    #         app = get_m2v_workflow()
    #         configuration: RunnableConfig = {"configurable": {
    #             "thread_id": "1", "temp_dir": temp_dir_path}}
    #         # 此处temp_dir是工作流对应的文件夹
    #         result = await app.ainvoke({"id": id, "product": product, "product_info": product_info, "model_images": model_images,
    #                                     "video_fragment_duration": video_fragment_duration, "video_output_path": video_output_path},
    #                                    config=configuration)
    #         return result

    async def process_video_fragment(self, product, product_info, video_fragment_duration, video_fragment: VideoFragment, result_dir, i2v_strategy):
        """处理单个视频片段的异步函数"""
        image = video_fragment.model_image
        video_positive_prompt, video_negative_prompt, video_url = await i2v_strategy_chain.execute_chain(
            product=product, product_info=product_info, img_path=image,
            img_info=video_fragment.model_image_info, duration=int(
                video_fragment_duration),
            resolution={"width": 1080, "height": 1920}, video_type=video_fragment.video_type, i2v_strategy=i2v_strategy)
        video_fragment.video_positive_prompt = video_positive_prompt
        video_fragment.video_negative_prompt = video_negative_prompt
        #  假如当前有文件则跳过
        video_url_v1 = os.path.join(
            result_dir, video_fragment.id, "video_url_v1.mp4")
        # 直到video_number对应的文件不存在
        video_data = get_url_data(video_url)
        with open(video_url_v1, "wb") as f:
            f.write(video_data)
        video_fragment.video_url_v1 = os.path.join(
            video_fragment.id, "video_url_v1.mp4")
        # 获取视频时长
        video_duration = get_video_duration(video_url_v1)
        video_fragment.video_duration = int(video_duration)
        return video_fragment

    @mv2_modify_tool
    async def change_model_image(self, index_list: list[int], model_image: str):
        """
        将模特图片切换为新的模特图片，然后重新生成视频片段
        Args:
            index(int): 视频片段索引
            model_image(str): 新的模特图片url
        """
        need_change_number = len(index_list)
        workflow_state = self.get_workflow_state()
        need_change_video_fragments = []
        for index in index_list:
            for video_fragment in workflow_state.video_fragments:
                if video_fragment.video_index == index:
                    need_change_video_fragments.append(video_fragment)
                    index_list.remove(index)
        if len(need_change_video_fragments) != need_change_number:
            raise HumanError(f"视频片段索引{index_list}不存在")
        result_dir = conf.get_path("m2v_workflow_result_dir")

        # 并发执行所有视频片段处理任务
        tasks = [self.process_video_fragment(workflow_state.product, workflow_state.product_info, workflow_state.video_fragment_duration, video_fragment, result_dir, workflow_state.i2v_strategy)
                 for video_fragment in need_change_video_fragments]
        await asyncio.gather(*tasks)


# 5.更改生成策略
 # 4.将模特图片切换为....(将模特图片切换为新的模特图片，然后重新生成视频片段)
