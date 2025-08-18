import json
from abc import ABC, abstractmethod
from config import conf


class TaskLibrary:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.task_list = []

    def add_task(self, task_description: str, task_input: str, task_execution_process: str):
        self.task_list.append(
            Task(task_description, task_input, task_execution_process))


class Task:
    def __init__(self, task_description: str, task_input: str, task_execution_process: list[tuple[str, str]]):
        self.task_description = task_description
        self.task_input = task_input
        self.task_execution_process = task_execution_process


class AdvertisementCreation(TaskLibrary):
    def __init__(self):
        name = "advertisement_creation"
        description = """
        在以下示例中，你被给予一个广告创作需求，你需要根据需求创作一个广告，并返回广告的图片，视频，文案。
        """
        super().__init__(name, description)


class TaskLibraryManager:
    def __init__(self):
        self.task_library_list = []

    def add_task_library(self, task_library: TaskLibrary):
        self.task_library_list.append(task_library)

    def add_task_library_from_json(self, json_file_path: str):
        """
        从json文件中加载任务库
        json文件的格式为：
        {
            "task_library_name": {
                "description": "任务库描述",
                "task_list": [
                    {"task_description": "任务描述", "task_input": "任务输入", "task_execution_process": "任务执行过程"}
                ]
            }
        }
        """
        with open(json_file_path, "r") as f:
            task_library_dict = json.load(f)
        for task_library_name, task_library_info in task_library_dict.items():
            task_library = TaskLibrary(
                task_library_name, task_library_info["description"])
            for task_info in task_library_info["task_list"]:
                task_library.add_task(
                    task_info["task_description"], task_info["task_input"], task_info["task_execution_process"])
            self.add_task_library(task_library)

    def task_retrieval(self, query: str):
        pass


task_library_manager = TaskLibraryManager()
task_library_manager.add_task_library_from_json(
    conf.get("ad_agent.task_library_json_path"))
