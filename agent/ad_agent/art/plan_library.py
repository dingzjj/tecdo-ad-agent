from config import conf
import json


class PlanLibrary:
    def __init__(self, name: str, plan_list: list[dict]):
        self.name = name
        self.plan_list = plan_list

    def add_plan(self, plan: dict):
        self.plan_list.append(plan)

    def __str__(self):
        return f"PlanLibrary(name={self.name}, description={self.description}, plan_list={self.plan_list})"

    def to_prompt(self):
        return f"{self.plan_list}"


class PlanLibraryManager:
    def __init__(self):
        self.plan_library_dict = {}

    def add_plan_library(self, plan_library: PlanLibrary):
        self.plan_library_dict[plan_library.name] = plan_library

    def add_plan_library_from_json(self, json_file_path: str):
        """
        从json文件中加载任务库
        """
        with open(json_file_path, "r") as f:
            plan_library_dict = json.load(f)
        for plan_library_name, plan_library_info in plan_library_dict.items():
            plan_library = PlanLibrary(
                name=plan_library_name, plan_list=plan_library_info["plan_list"])
            self.add_plan_library(plan_library)

    def get_prompt_from_plan_library(self, plan_library_name: str):
        return self.plan_library_dict[plan_library_name].to_prompt()


plan_library_manager = PlanLibraryManager()
plan_library_manager.add_plan_library_from_json(
    conf.get_path("ad_agent.plan_library_json_path"))
