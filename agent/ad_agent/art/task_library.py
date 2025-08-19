from typing import List, Dict
import json
from abc import ABC, abstractmethod
from config import conf


class Task:
    def __init__(self, task_input: str, overhead_information: Dict[str, str], task_execution_process: List[Dict[str, str]], task_output: str):
        self.task_input = task_input
        self.overhead_information = overhead_information
        self.task_execution_process = task_execution_process
        self.task_output = task_output

    @classmethod
    def from_json(cls, json_data: str):
        """从JSON字符串构造Task对象"""
        data = json.loads(json_data)
        return cls(
            task_input=data["task_input"],
            overhead_information=data["overhead_information"],
            task_execution_process=data["task_execution_process"],
            task_output=data["task_output"]
        )

    def to_json(self) -> str:
        """将Task对象转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=4)

    def to_dict(self) -> dict:
        """将Task对象转换为字典"""
        return {
            "task_input": self.task_input,
            "overhead_information": self.overhead_information,
            "task_execution_process": self.task_execution_process,
            "task_output": self.task_output
        }

    def __str__(self) -> str:
        """返回json string"""
        return self.to_json()


class TaskLibrary:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.task_list: list[Task] = []

    def add_task(self, task: Task):
        self.task_list.append(task)

    def __str__(self):
        # 将任务库的任务列表转换为JSON字符串形式
        task_details = "\n".join(str(task) for task in self.task_list)
        return (
            f"任务库名称：{self.name}\n"
            f"任务库描述：{self.description}\n"
            f"任务库任务示例：\n{task_details if task_details else '没有任务'}"
        )


class TaskLibraryManager:
    def __init__(self):
        self.task_library_list = []

    def add_task_library(self, task_library: TaskLibrary):
        self.task_library_list.append(task_library)

    def add_task_library_from_json(self, json_file_path: str):
        """
        从json文件中加载任务库
        """
        with open(json_file_path, "r") as f:
            task_library_dict = json.load(f)
        for task_library_name, task_library_info in task_library_dict.items():
            task_library = TaskLibrary(
                name=task_library_name, description=task_library_info["description"])
            for task_info in task_library_info["task_list"]:
                task_library.add_task(
                    Task.from_json(json.dumps(task_info)))
            self.add_task_library(task_library)

    def get_prompt_from_task_library(self, task_library_list: list[TaskLibrary]):
        # 将TaskLibrary给json string
        result = ""
        for task_library in task_library_list:
            result += str(task_library)
        return result

    def task_retrieval(self, query: str):
        return self.get_prompt_from_task_library(self.task_library_list)


task_library_manager = TaskLibraryManager()
task_library_manager.add_task_library_from_json(
    conf.get("ad_agent.task_library_json_path"))
