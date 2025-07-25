from config import logger
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
import os
import mimetypes
from typing import List, Union
import base64


def create_client(api_key: str) -> ElevenLabs:
    """
    创建并返回一个 ElevenLabs 客户端实例。

    参数:
        api_key (str): 用于认证的 API 密钥。

    返回:
        ElevenLabs: 初始化后的 ElevenLabs 客户端对象。
    """
    try:
        client = ElevenLabs(api_key=api_key)
        return client
    except Exception as e:
        print(f"❌ 创建客户端失败: {e}")
        raise


def prepare_audio_files(file_paths: Union[str, List[str]]) -> List[tuple]:
    """
    将音频文件转换为 (name, content, mime_type) 格式的列表，用于上传至 ElevenLabs。

    参数:
        file_paths (Union[str, List[str]]): 单个或多个音频文件路径。

    返回:
        List[tuple]: 包含文件名、二进制内容和 MIME 类型的元组列表。
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    files_info = []
    for file_path in file_paths:
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")

            # 读取文件内容
            with open(file_path, "rb") as f:
                file_content = f.read()

            # 获取 MIME 类型
            file_name = os.path.basename(file_path)
            file_type, _ = mimetypes.guess_type(file_path)
            if not file_type or not file_type.startswith("audio/"):
                raise ValueError(f"不支持的文件类型: {file_type}，路径: {file_path}")

            file_tuple = (file_name, file_content, file_type)
            files_info.append(file_tuple)

        except Exception as e:
            print(f"❌ 处理文件 {file_path} 出错: {e}")
            continue  # 可以选择跳过无效文件继续执行

    if not files_info:
        raise ValueError("❌ 没有有效文件可用于上传")

    return files_info


def clone_voice(
    client: ElevenLabs,
    voice_name: str,
    voice_desc: str,
    source_voice_files: Union[str, List[str]],
) -> str:
    """
    使用指定的音频样本克隆一个新的语音模型。

    参数:
        client (ElevenLabs): 已初始化的 ElevenLabs 客户端。
        name (str): 音色名称
        desc (str): 音色描述
        source_voice_files (Union[str, List[str]]): 一个或多个音频文件路径。

    返回:
        str: 克隆成功后返回的 voice_id。
    """
    try:
        # 接收文件信息
        files = prepare_audio_files(source_voice_files)

        print("🔄 正在克隆语音...")
        # 调用接口创建克隆语音
        custom_voice = client.voices.ivc.create(
            name=voice_name,
            description=voice_desc,
            files=files,
        )
        print(f"✅ 语音克隆成功，voice_id: {custom_voice.voice_id}")
        return custom_voice.voice_id
    except Exception as e:
        print(f"❌ 克隆语音失败: {e}")
        raise


def get_voice(client: ElevenLabs, voice_name: str):
    """
    通过voice_name来获取口音
    """
    pass


def set_voice(
    stability: float = 0.71,
    similarity_boost: float = 0.5,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    speed: float = 1.0,
) -> dict:
    """
    设置音色参数（确保所有参数都被保留，包括0.0等有效值）

    参数：
        stability (float): 控制语调稳定性（0.0 ~ 1.0），值越高语调越稳定. Defaults to 0.71.
        similarity_boost (float): 增强语音与原始音色相似性（0.0 ~ 1.0）. Defaults to 0.5.
        style (float): 控制语音表达情绪或风格强度（0.0 ~ 1.0）. Defaults to 0.0.
        use_speaker_boost (bool): 是否启用说话人增强功能. Defaults to True.
        speed (float): 控制语音速度. Defaults to 1.0.

    返回:
        dict: 包含所有语音参数的字典（确保不遗漏任何参数）
    """
    # 直接包含所有参数，无论值是多少（0.0是合法值，应保留）
    return {
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "use_speaker_boost": use_speaker_boost,
        "speed": speed,
    }


def text_to_speech(
    client: ElevenLabs,
    voice_id: str,
    text: str,
    filename: str,
    voice_settings: dict,
):
    """
    使用指定语音 ID 将文本转换为语音，并保存为 MP3 文件。
    filename: 文件名(绝对路径，包含后缀)
    """
    try:
        # print("🔄 正在进行文本转语音...")
        if voice_settings is None:
            # 无自定义设置时，使用API默认值
            response = client.text_to_speech.convert_with_timestamps(
                voice_id=voice_id, text=text, model_id="eleven_multilingual_v2"
            )
        else:
            # 传入所有参数（包括0.0），确保VoiceSettings不缺失
            response = client.text_to_speech.convert_with_timestamps(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=voice_settings["stability"],
                    similarity_boost=voice_settings["similarity_boost"],
                    style=voice_settings["style"],
                    use_speaker_boost=voice_settings["use_speaker_boost"],
                    speed=voice_settings["speed"],
                ),
            )

        # 保存音频
        audio_bytes = base64.b64decode(response.audio_base_64)
        with open(filename, "wb") as f:
            f.write(audio_bytes)
        print(f"✅ 音频已保存至 {filename}")
    except Exception as e:
        print(f"❌ 文本转语音失败: {e}")
        raise e


def get_voice_id(client: ElevenLabs, voice_name: str, default_voice_name: str) -> str:
    """
    通过 voice_name 获取指定 voice_id 的语音信息
    """
    default_voice_id = ""
    response = client.voices.get_all()
    for voice in response.voices:
        if voice_name == voice.name:
            return voice.voice_id
        if default_voice_name == voice.name:
            default_voice_id = voice.voice_id
    return default_voice_id


def text_to_speech_with_elevenlabs(elevenlabs_api_key, text: str, filename: str, voice_name: str, speed: float = 1.0):
    """
    使用 ElevenLabs 将文本转换为语音，并保存为 MP3 文件。
    voice_name: 音色名称(语音库存在的音色名)
    stability (float): 控制语调稳定性（0.0 ~ 1.0），值越高语调越稳定. Defaults to 0.71.
    similarity_boost (float): 增强语音与原始音色相似性（0.0 ~ 1.0）. Defaults to 0.5.
    style (float): 控制语音表达情绪或风格强度（0.0 ~ 1.0）. Defaults to 0.0.
    use_speaker_boost (bool): 是否启用说话人增强功能. Defaults to True.
    speed (float): 控制语音速度. Defaults to 1.0.
    filename: 文件名(绝对路径，包含后缀)
    """
    stability = 0.71
    similarity_boost = 0.5
    style = 0.0
    use_speaker_boost = True
    try:
        # 初始化客户端
        client = create_client(elevenlabs_api_key)
        # 通过voice_name来获取口音
        voice_id = get_voice_id(client, voice_name, "Eric")
        # 配置音色
        voice_settings = set_voice(
            stability, similarity_boost, style, use_speaker_boost, speed=speed
        )
        # 文本转语音
        text_to_speech(client, voice_id, text, filename, voice_settings)
    except Exception as e:
        logger.error(f"文本转语音失败: {e}")
        raise e
