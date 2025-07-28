import os
from config import conf
from modules.hook import load_app
import gradio as gr
from agent.third_part.i2v import action_types
from modules.hook import change_file
from modules.hook import m2v_v1_generate, m2v_v1_clear, m2v_v2_clear
from modules.hook_m2v import m2v_v2_generate, m2v_v2_video_stitching
from modules.hook_ad_agent import send_message_to_ad_agent
from modules.hook import user_input_func
from modules.hook import m2v_v2_add_image_btn_click, m2v_v2_remove_image_btn_click
from pojo import user_id
image_container_init_number = 0


def create_m2v_v2_image_container(group_num: int):
    """创建支持动态添加和删除的图片组件"""
    container_img = []
    container_image_item = []
    container_positive_prompt = []
    container_negative_prompt = []
    container_action_type = []
    container_video_show_box = []
    with gr.Row():
        with gr.Column():
            gr.Markdown(f"## 📸 第{group_num}组图片输入区域")
            with gr.Column(elem_id=f"v2_image_container_{group_num}"):
                container_image_number = gr.State(
                    image_container_init_number)
                with gr.Row():
                    gr.Markdown(value=f"### 图片组 {group_num}")
                # 生成按钮
                    generate_btn = gr.Button(
                        "🎬 视频拼接，生成视频",
                        variant="primary",
                        size="sm",
                        elem_classes=["primary-btn"]
                    )
                    clear_btn = gr.Button(
                        "🗑️ 清空",
                        variant="secondary",
                        size="sm",
                        elem_classes=["clear-btn"]
                    )

                # 图片容器
                # 初始的5张图片
                for i in range(1, 6):
                    if i <= container_image_number.value:
                        render = True
                    else:
                        render = False
                    with gr.Column(elem_id=f"image_container_{group_num}", visible=render) as image_container:
                        with gr.Column(elem_id=f"image_item_{group_num}_{i}"):
                            with gr.Row():
                                with gr.Column(scale=1):
                                    img = gr.Image(
                                        label=f"图片 {i}",
                                        sources=["upload"],
                                        type="filepath",
                                        height=180,
                                        interactive=True,
                                        elem_classes=["image-upload"],
                                        elem_id=f"m2v_v2_group_{
                                            group_num}_img_{i}"
                                    )
                                with gr.Column(scale=1):
                                    positive_prompt = gr.Textbox(
                                        label=f"正向提示词 {i}",
                                        placeholder=f"请输入图片 {i} 的正向提示词...",
                                        elem_classes=["prompt-input"],
                                        interactive=True,
                                        elem_id=f"m2v_v2_group_{
                                            group_num}_positive_prompt_{i}"
                                    )
                                    negative_prompt = gr.Textbox(
                                        label=f"负向提示词 {i}",
                                        placeholder=f"请输入图片 {i} 的负向提示词...",
                                        elem_classes=["prompt-input"],
                                        interactive=True,
                                        elem_id=f"m2v_v2_group_{
                                            group_num}_negative_prompt_{i}"
                                    )
                                with gr.Column(scale=1):
                                    action_type_select_box = gr.Radio(interactive=True,
                                                                      choices=action_types, label="模特动作选择", elem_classes=["action-type"], elem_id=f"m2v_v2_group_{group_num}_action_type_{i}")
                                with gr.Column(scale=1):
                                    video_show_box = gr.Video(
                                        label=f"视频 {i}",
                                        sources=["upload"],
                                        height=180,
                                        elem_classes=["video-show-box"],
                                        elem_id=f"m2v_v2_group_{
                                            group_num}_video_show_box_{i}"
                                    )

                            item_generate_btn = gr.Button(
                                f"🎬 生成视频",
                                variant="primary",
                                size="lg",
                                elem_id=f"m2v_v2_group_{
                                    group_num}_generate_btn",
                                elem_classes=["primary-btn"],
                                interactive=True
                            )
                        container_image_item.append(image_container)
                        container_img.append(img)
                        container_positive_prompt.append(positive_prompt)
                        container_negative_prompt.append(negative_prompt)
                        container_action_type.append(action_type_select_box)
                        container_video_show_box.append(video_show_box)
                with gr.Row():
                    container_add_btn = gr.Button(
                        "➕ 添加图片",
                        variant="secondary",
                        elem_classes=["add-image-btn"],
                        elem_id=f"m2v_v2_group_{group_num}_container_add_btn"
                    )

                    container_remove_btn = gr.Button(
                        "➖ 删除最后一张图片",
                        variant="secondary",
                        elem_classes=["remove-image-btn"],
                        elem_id=f"m2v_v2_group_{
                            group_num}_container_remove_btn",
                        interactive=False
                    )
        with gr.Column():
            gr.Markdown(f"## 🎥 第{group_num}组视频输出区域")

            with gr.Column():
                gr.Markdown("### 视频 1")
                video_show_box = gr.Video(
                    label=f"第{group_num}组生成的视频",
                    height=200,
                    sources=["upload"],
                    elem_classes=["video-container"]
                )
            # 监听器
            item_generate_btn.click(fn=m2v_v2_generate, inputs=[
                img, positive_prompt, negative_prompt, action_type_select_box], outputs=[video_show_box])

            generate_btn_click_input = [container_image_number]
            generate_btn_click_input.extend(container_video_show_box)
            generate_btn.click(
                fn=m2v_v2_video_stitching, inputs=generate_btn_click_input, outputs=[video_show_box])

            clear_btn_click_output = list(container_img)
            clear_btn_click_output.extend(
                container_positive_prompt)
            clear_btn_click_output.extend(
                container_negative_prompt)
            clear_btn_click_output.extend(
                container_action_type)
            clear_btn_click_output.extend(
                container_video_show_box)
            clear_btn.click(
                fn=m2v_v2_clear, inputs=[], outputs=clear_btn_click_output)
            # 添加/删除图片 按钮点击事件

            container_add_btn_click_output = [
                container_image_number]
            container_add_btn_click_output.extend(
                container_image_item)
            container_add_btn_click_output.append(
                container_add_btn)
            container_add_btn_click_output.append(
                container_remove_btn)
            container_add_btn.click(fn=m2v_v2_add_image_btn_click, inputs=[
                container_image_number], outputs=container_add_btn_click_output)
            container_remove_btn.click(fn=m2v_v2_remove_image_btn_click, inputs=[
                container_image_number], outputs=container_add_btn_click_output)

        return container_image_item, container_img, container_positive_prompt, container_negative_prompt, container_action_type, container_video_show_box


def create_v1_image_container(group_num: int):
    """创建简单的图片组件，只用于v1版本"""
    container_img = []
    with gr.Column(elem_id=f"v1_image_container_{group_num}"):
        gr.Markdown(f"### 图片组 {group_num}")
        with gr.Row():  # ✅ 使用 Row 来并排布局
            for i in range(1, 6):  # 5张图片
                img = gr.Image(
                    label=f"图片 {i}",
                    type="filepath",
                    sources=["upload"],
                    height=150,
                    min_width=100,
                    width="20%",  # 推荐使用 px，确保一致
                    elem_id=f"simple_image_container_{group_num}_img_{i}",
                    elem_classes=["image-upload"]
                )
                container_img.append(img)
    return container_img


with gr.Blocks() as demo:
    is_end = gr.State(True)
    m2v_v1_group_number = gr.State(3)
    m2v_v1_group_img_container_number = gr.State(5)
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
                m2v_v1_group1_container_img = create_v1_image_container(
                    1)
                gr.Markdown("---")
                m2v_v1_group2_container_img = create_v1_image_container(
                    2)
                gr.Markdown("---")
                m2v_v1_group3_container_img = create_v1_image_container(
                    3)
            with gr.Column(scale=2):
                gr.Markdown("## 🎥 视频输出区域")
                with gr.Column():
                    gr.Markdown("### 视频 1")
                    m2v_v1_video1 = gr.Video(
                        label="第一组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-show-box"]
                    )
                    # m2v_v1_download1 = gr.DownloadButton(
                    #     "下载视频 1",
                    #     variant="secondary",
                    #     elem_classes=["download-btn"]
                    # )

                gr.Markdown("---")

                with gr.Column():
                    gr.Markdown("### 视频 2")
                    m2v_v1_video2 = gr.Video(
                        label="第二组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-show-box"]
                    )
                    # m2v_v1_download2 = gr.DownloadButton(
                    #     "下载视频 2",
                    #     variant="secondary",
                    #     elem_classes=["download-btn"]
                    # )

                gr.Markdown("---")

                with gr.Column():
                    gr.Markdown("### 视频 3")
                    m2v_v1_video3 = gr.Video(
                        label="第三组生成的视频",
                        height=200,
                        sources=["upload"],
                        elem_classes=["video-show-box"]
                    )
                    # m2v_v1_download3 = gr.DownloadButton(
                    #     "下载视频 3",
                    #     variant="secondary",
                    #     elem_classes=["download-btn"]
                    # )
    with gr.Tab("model image to video v2"):
        with gr.Column(scale=3):
            # 左侧：图片和提示词输入

            m2v_v2_group1_container_image_item, m2v_v2_group1_container_img, m2v_v2_v2_group1_container_positive_prompt, m2v_v2_v2_group1_container_negative_prompt, m2v_v2_v2_group1_container_action_type, m2v_v2_v2_group1_container_video_show_box = create_m2v_v2_image_container(
                1)

            gr.Markdown("---")
            m2v_v2_group2_container_image_item, m2v_v2_group2_container_img, m2v_v2_group2_container_positive_prompt, m2v_v2_group2_container_negative_prompt, m2v_v2_group2_container_action_type, m2v_v2_group2_container_video_show_box = create_m2v_v2_image_container(
                2)
            gr.Markdown("---")

            # 第三组 - 使用终极动态组件
            m2v_v2_group3_container_image_item, m2v_v2_group3_container_img, m2v_v2_group3_container_positive_prompt, m2v_v2_group3_container_negative_prompt, m2v_v2_group3_container_action_type, m2v_v2_group3_container_video_show_box = create_m2v_v2_image_container(
                3)
    with gr.Tab("ad agent"):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 会话管理")

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
                    ad_agent_file_explorer = gr.FileExplorer(label="文件管理", root_dir=f"{os.path.join(
                        conf.get_path("user_data_dir"), user_id)}", file_count="single", ignore_glob="*.json")

                    with gr.Group():
                        with gr.Row():
                            with gr.Column():
                                video_display = gr.Video(
                                    label="视频展示", value=None, sources=["upload"])
                            with gr.Column():
                                image_display = gr.Image(
                                    label="图片展示", value=None, sources=["upload"])

    m2v_v1_clear_btn_output = list(m2v_v1_group1_container_img)
    m2v_v1_clear_btn_output.extend(m2v_v1_group2_container_img)
    m2v_v1_clear_btn_output.extend(m2v_v1_group3_container_img)
    m2v_v1_clear_btn.click(fn=m2v_v1_clear, inputs=[m2v_v1_group_number, m2v_v1_group_img_container_number],
                           outputs=m2v_v1_clear_btn_output)

    ad_agent_file_explorer.change(
        fn=change_file, inputs=[ad_agent_file_explorer], outputs=[video_display, image_display])

    m2v_v1_generate_input = [m2v_v1_positive_prompt, m2v_v1_negative_prompt]
    m2v_v1_generate_input.extend(m2v_v1_group1_container_img)
    m2v_v1_generate_input.extend(m2v_v1_group2_container_img)
    m2v_v1_generate_input.extend(m2v_v1_group3_container_img)
    m2v_v1_generate_btn.click(
        fn=m2v_v1_generate, inputs=(m2v_v1_generate_input),
        outputs=[m2v_v1_video1, m2v_v1_video2, m2v_v1_video3])

    ad_agent_user_input.submit(fn=user_input_func, inputs=[ad_agent_user_input, chatbot], outputs=[chatbot]).then(
        fn=send_message_to_ad_agent, inputs=[ad_agent_user_input, chatbot, is_end], outputs=[chatbot, is_end])
    demo.load(fn=load_app, inputs=[], outputs=[chatbot])


demo.queue(max_size=10, default_concurrency_limit=5)
demo.launch(server_name="0.0.0.0", server_port=6009, share=False)
