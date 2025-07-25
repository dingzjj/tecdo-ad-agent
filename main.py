import os
from config import conf
from modules.hook import load_app
import gradio as gr
from agent.third_part.i2v import action_types
from modules.hook import change_file
from modules.hook import m2v_v1_generate, m2v_v1_clear, m2v_v2_generate, m2v_v2_clear, ad_agent_send
from modules.hook_ad_agent import send_message_to_ad_agent
from modules.hook import user_input_func


def create_image_prompt_components(group_num: int):
    """创建一组图片和提示词输入组件"""
    components_img = []

    with gr.Column():
        gr.Markdown(f"### 图片组 {group_num}")
        for i in range(1, 6):  # 5张图片
            with gr.Row():
                with gr.Column(scale=2):
                    img = gr.Image(
                        label=f"图片 {i}",
                        type="filepath",
                        sources=["upload"],
                        height=150,
                        elem_classes=["image-upload"]
                    )
                    components_img.append(img)
    return components_img


def create_image_prompt_action_type_video_components(group_num: int):
    """创建一组图片和提示词输入组件"""
    components_img = []
    components_prompt = []
    components_video_show_box = []

    with gr.Column():
        gr.Markdown(f"### 图片组 {group_num}")

        for i in range(1, 6):  # 5张图片
            with gr.Row():
                with gr.Column(scale=2):
                    img = gr.Image(
                        label=f"图片 {i}",
                        sources=["upload"],
                        type="filepath",
                        height=150,
                        elem_classes=["image-upload"]
                    )
                with gr.Column(scale=3):
                    prompt = gr.Textbox(
                        label=f"提示词 {i}",
                        placeholder=f"请输入图片 {i} 的提示词...",
                        lines=2,
                        max_lines=3,
                        elem_classes=["prompt-input"]
                    )
                with gr.Column(scale=1):
                    video_show_box = gr.Radio(
                        choices=action_types, label="模特动作选择")
                with gr.Column(scale=1):
                    video_show_box = gr.Video(
                        label=f"视频 {i}",
                        sources=["upload"],
                        elem_classes=["video-show-box"]
                    )
            with gr.Row():
                gr.Button(
                    f"🎬 生成视频{i}",
                    variant="primary",
                    size="lg",
                    elem_classes=["primary-btn"],
                    interactive=True
                )

            components_img.append(img)
            components_prompt.append(prompt)
            components_video_show_box.append(video_show_box)

    return components_img, components_prompt, components_video_show_box


with gr.Blocks() as demo:
    user_id = gr.State("1")
    is_end = gr.State(True)
    with gr.Tab("model image to video v1"):
        with gr.Row():
            # 左侧：图片和提示词输入
            with gr.Column(scale=3):
                gr.Markdown("## 📸 图片输入区域")
                with gr.Row():
                    m2v_v1_generate_btn = gr.Button(
                        "🎬 生成视频",
                        variant="primary",
                        size="lg",
                        elem_classes=["primary-btn"]
                    )
                    m2v_v1_clear_btn = gr.Button(
                        "🗑️ 清空",
                        variant="secondary",
                        elem_classes=["clear-btn"]
                    )
                with gr.Row():
                    m2v_v1_positive_prompt = gr.Textbox(
                        label="正向提示词",
                        placeholder="请输入提示词...",
                        lines=2,
                        max_lines=3,
                        elem_classes=["prompt-input"]
                    )
                    m2v_v1_negative_prompt = gr.Textbox(
                        label="负向提示词",
                        placeholder="请输入提示词...",
                        lines=2,
                        max_lines=3,
                        elem_classes=["prompt-input"]
                    )
                gr.Markdown("---")
                m2v_v1_group1_components_img = create_image_prompt_components(
                    1)
                gr.Markdown("---")
                m2v_v1_group2_components_img = create_image_prompt_components(
                    2)
                gr.Markdown("---")
                m2v_v1_group3_components_img = create_image_prompt_components(
                    3)
            with gr.Column(scale=2):
                gr.Markdown("## 🎥 视频输出区域")
                with gr.Column():
                    gr.Markdown("### 视频 1")
                    m2v_v1_video1 = gr.Video(
                        label="第一组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-container"]
                    )
                    m2v_v1_download1 = gr.DownloadButton(
                        "下载视频 1",
                        variant="secondary",
                        elem_classes=["download-btn"]
                    )

                gr.Markdown("---")

                with gr.Column():
                    gr.Markdown("### 视频 2")
                    m2v_v1_video2 = gr.Video(
                        label="第二组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-container"]
                    )
                    m2v_v1_download2 = gr.DownloadButton(
                        "下载视频 2",
                        variant="secondary",
                        elem_classes=["download-btn"]
                    )

                gr.Markdown("---")

                with gr.Column():
                    gr.Markdown("### 视频 3")
                    m2v_v1_video3 = gr.Video(
                        label="第三组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-container"]
                    )
                    m2v_v1_download3 = gr.DownloadButton(
                        "下载视频 3",
                        variant="secondary",
                        elem_classes=["download-btn"]
                    )
    with gr.Tab("model image to video v2"):
        with gr.Row():
            # 左侧：图片和提示词输入
            with gr.Column(scale=3):
                gr.Markdown("## 📸 图片输入区域")

                # 生成按钮
                with gr.Row():
                    m2v_v2_generate_btn = gr.Button(
                        "🎬 生成视频",
                        variant="primary",
                        size="lg",
                        elem_classes=["primary-btn"]
                    )
                    m2v_v2_clear_btn = gr.Button(
                        "🗑️ 清空",
                        variant="secondary",
                        elem_classes=["clear-btn"]
                    )

                # 第一组
                m2v_v2_group1_components_img, m2v_v2_group1_components_prompt, m2v_v2_group1_components_video_show_box = create_image_prompt_action_type_video_components(
                    1)

                gr.Markdown("---")

                # 第二组
                m2v_v2_group2_components_img, m2v_v2_group2_components_prompt, m2v_v2_group2_components_video_show_box = create_image_prompt_action_type_video_components(
                    2)

                gr.Markdown("---")

                # 第三组
                m2v_v2_group3_components_img, m2v_v2_group3_components_prompt, m2v_v2_group3_components_video_show_box = create_image_prompt_action_type_video_components(
                    3)

            # 右侧：视频输出
            with gr.Column(scale=2):
                gr.Markdown("## 🎥 视频输出区域")

                with gr.Column():
                    gr.Markdown("### 视频 1")
                    m2v_v2_video1 = gr.Video(
                        label="第一组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-container"]
                    )
                    m2v_v2_download1 = gr.DownloadButton(
                        "下载视频 1",
                        variant="secondary",
                        elem_classes=["download-btn"]
                    )

                gr.Markdown("---")

                with gr.Column():
                    gr.Markdown("### 视频 2")
                    m2v_v2_video2 = gr.Video(
                        label="第二组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-container"]
                    )
                    m2v_v2_download2 = gr.DownloadButton(
                        "下载视频 2",
                        variant="secondary",
                        elem_classes=["download-btn"]
                    )

                gr.Markdown("---")

                with gr.Column():
                    gr.Markdown("### 视频 3")
                    m2v_v2_video3 = gr.Video(
                        label="第三组生成的视频",
                        sources=["upload"],
                        height=200,
                        elem_classes=["video-container"]
                    )
                    m2v_v2_download3 = gr.DownloadButton(
                        "下载视频 3",
                        variant="secondary",
                        elem_classes=["download-btn"]
                    )
    with gr.Tab("ad agent"):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 历史对话区域")
            with gr.Column(scale=2):
                gr.Markdown("## 聊天区域")
                chatbot = gr.Chatbot(
                    label="聊天记录",
                    value=[],
                    type="messages",
                    elem_classes=["chatbot-container"]
                )

                ad_agent_user_input = gr.MultimodalTextbox(
                    label="",
                    placeholder="请输入内容...",
                    file_count="multiple",
                    elem_id="ad_agent_user_input",
                    elem_classes=["user-input"]
                )
            with gr.Column(scale=2):
                gr.Markdown("## 文件管理")
                with gr.Group(elem_id="file_explorer_group"):
                    ad_agent_file_explorer = gr.FileExplorer(
                        label="文件管理", root_dir=f"{os.path.join(conf.get_path("user_data_dir"), str(user_id.value))}", file_count="single", ignore_glob="*.json")
                    with gr.Group():
                        with gr.Row():
                            with gr.Column():
                                video_display = gr.Video(
                                    label="视频展示", value=None, sources=["upload"])
                            with gr.Column():
                                image_display = gr.Image(
                                    label="图片展示", value=None, sources=["upload"])

    ad_agent_file_explorer.change(
        fn=change_file, inputs=[ad_agent_file_explorer, user_id], outputs=[video_display, image_display])

    m2v_v1_generate_input = [
        user_id, m2v_v1_positive_prompt, m2v_v1_negative_prompt]
    m2v_v1_generate_input.extend(m2v_v1_group1_components_img)
    m2v_v1_generate_input.extend(m2v_v1_group2_components_img)
    m2v_v1_generate_input.extend(m2v_v1_group3_components_img)
    m2v_v1_generate_btn.click(
        fn=m2v_v1_generate, inputs=(m2v_v1_generate_input),
        outputs=[m2v_v1_video1, m2v_v1_video2, m2v_v1_video3])

    ad_agent_user_input.submit(fn=user_input_func, inputs=[ad_agent_user_input, chatbot], outputs=[chatbot]).then(
        fn=send_message_to_ad_agent, inputs=[ad_agent_user_input, chatbot, user_id, is_end], outputs=[chatbot, is_end])
    demo.load(fn=load_app, inputs=[user_id], outputs=[chatbot])
demo.launch(server_name="0.0.0.0", server_port=6005, share=False)
