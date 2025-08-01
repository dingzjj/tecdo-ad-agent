# 生成对应图片的prompt

"""
人物非常规角色且有强烈对比：主角不再是传统英雄，而是反差强烈、出人意料的人设，如穿西装的中年人、沉迷游戏的囚犯、战场中的宅男等，他们拿着朝摄像头方向显示的平板电脑。而其身边则是很多与主角有着强烈对比的人物，比如野人、壮汉、斯巴达士兵等等。
环境必须构成压迫或冲突源：场景不能平静舒适，必须存在“威胁”或“限制”，如牢笼、战场、陷阱、火山边缘等，用以突出角色的反常行为和情绪张力。
画面必须强戏剧性：包含激烈冲突、紧张动作、荒谬反差等。
情绪必须张力：加入紧张、喜感或不合理氛围。
游戏露出必须巧妙融合：游戏画面应该显示在平板电脑中。
"""
from agent.llm import chat_with_gemini_in_vertexai, get_gemini_multimodal_model
from agent.game_ad_agent.prompt import GENERATE_IMG_PROMPT_SYSTEM_PROMPT_EN, GENERATE_IMG_PROMPT_HUMAN_PROMPT_EN, GENERATE_IMG_PROMPT_SCHEMA
import json


def generate_img_prompt(scene_description: str) -> str:
    multimodal_model = get_gemini_multimodal_model(
        GENERATE_IMG_PROMPT_SYSTEM_PROMPT_EN, GENERATE_IMG_PROMPT_SCHEMA)

    response = multimodal_model.generate_content(
        [
            GENERATE_IMG_PROMPT_HUMAN_PROMPT_EN.format(
                scene_description=scene_description)
        ]
    )
    content = response.candidates[0].content.parts[0].text
    content = json.loads(content)
    return content["positive_prompt"], content["negative_prompt"]
