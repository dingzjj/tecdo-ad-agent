from modules.hook_e_commerce_agent import bgi_product_gallery_add_btn_click, bgi_product_gallery_remove_btn_click
from modules.hook_game_ad import get_game_ad_video_mid_state, step1_submit, step2_submit, step3_submit, update_game_ad_video_mid_state
from modules.hook import load_app
import gradio as gr
from agent.third_part.i2v import action_types
from modules.hook import m2v_v1_generate, m2v_v1_clear, m2v_v2_clear
from modules.hook_m2v import m2v_v2_generate, m2v_v2_video_stitching
from modules.hook_ad_agent import send_message_to_art_ad_agent
from modules.hook import user_input_func
from modules.hook import m2v_v2_add_image_btn_click, m2v_v2_remove_image_btn_click
from modules.hook_e_commerce_agent import bgi_submit
from modules.hook_search import google_play_search, amazon_search
image_container_init_number = 0

# v1表示文生图生成的图片
# v2表示视频(without 游戏视频)
# v3表示视频(with 游戏视频)
# 所有文件都存在user_id目录下


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


with gr.Blocks(css_paths=["web_assets/styles.css"]) as demo:
    m2v_v1_group_number = gr.State(3)
    m2v_v1_group_img_container_number = gr.State(5)
    # 定义状态变量，用于存储聊天历史
    chatbot_history = gr.State([])
    with gr.Tab("ad agent"):
        user_material_id = gr.State(1)

        with gr.Row():
            # with gr.Column(scale=1):
            #     gr.Markdown("## 会话管理")
            with gr.Column(scale=2):
                gr.Markdown("## ad agent 聊天区域")
                chatbot = gr.Chatbot(
                    label="聊天记录",
                    value=[],
                    type="messages",
                    height=700,
                    elem_classes=["chatbot-container"],
                    show_label=False
                )

                ad_agent_user_input = gr.MultimodalTextbox(
                    label=None,
                    placeholder="请输入内容...",
                    file_count="multiple",
                    elem_id="ad_agent_user_input",
                    elem_classes=["user-input"],
                )
            with gr.Column(scale=2):
                # 素材库
                gr.Markdown("## 素材库")
                ad_agent_material_library = gr.Gallery(
                    label="素材库",
                    file_types=["image"],
                    type="filepath",
                    interactive=False,
                )

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

    with gr.Tab("game ad agent"):
        game_ad_agent_mid_video = gr.State("")
        img_of_video_v2 = gr.State("")
        user_id = gr.State("main")
        all_img_v1_list = gr.State({})
        all_video_v2_list = gr.State([])
        game_video_input_width = gr.State(0)
        game_video_input_height = gr.State(0)

        with gr.Row():
            # 游戏视频与游戏封面输入
            with gr.Column(scale=1):
                gr.Markdown("## 🎥 游戏视频输入")
                game_video_input = gr.Video(
                    label="游戏视频",
                    height=200,
                    sources=["upload"],
                    interactive=True,
                    elem_classes=["video-show-box"]
                )
                game_cover_input = gr.Image(
                    label="游戏封面",
                    height=200,
                    type="filepath",
                    sources=["upload"],
                    interactive=True,
                    elem_classes=["image-show-box"]
                )
                game_description_input = gr.Textbox(
                    label="游戏视频描述",
                    placeholder="请输入游戏视频描述...",
                    elem_classes=["game-description-input"],
                    interactive=True
                )
                step1_submit_btn = gr.Button("提交")
            # 游戏广告视频输出
            with gr.Column(scale=1):
                gr.Markdown("## 🎥 画面选择")
                img_v1_gallery = gr.Gallery(
                    value=[],
                    label="画面选择",
                    columns=3,
                    rows=3,
                    height=200
                )
                img_v1_gallery_select_box = gr.CheckboxGroup(
                    label="选择画面",
                    choices=[],
                    value=[],
                    type="value",
                    interactive=True
                )
                step2_submit_btn = gr.Button("提交")

            with gr.Column(scale=1):
                gr.Markdown("## 🎥 确定游戏画面位置")
                img_of_video_v2_annotated = gr.AnnotatedImage(
                    show_label=False,
                    value=None,
                    height=200,
                    elem_classes=["annotated-image-show-box"]
                )
                x_slider = gr.Slider(
                    label="x",
                    minimum=0,
                    maximum=1,
                    step=1,
                    value=0
                )
                y_slider = gr.Slider(
                    label="y",
                    minimum=0,
                    maximum=1,
                    step=1,
                    value=0
                )
                width_slider = gr.Slider(
                    label="width",
                    minimum=0,
                    maximum=1,
                    step=1,
                    value=0
                )
                step3_submit_btn = gr.Button("提交")
                # 在视频上调动游戏画面

            with gr.Column(scale=1):
                gr.Markdown("## 🎥 游戏广告视频输出")
                with gr.Row():
                    game_ad_video_final_output = gr.Video(
                        label="游戏广告视频",
                        height=200,
                        interactive=False,
                        elem_classes=["video-show-box"]
                    )
    with gr.Tab("批量生成图片"):
        # batch_generate_images bgi
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 输入商品参考图（越多越好）")
                with gr.Row():
                    with gr.Column(scale=1, min_width=200, elem_classes=["bgi_product_image_box"]):
                        bgi_product_gallery_zm = gr.Gallery(
                            label="商品正面",
                            height=200,
                            file_types=["image"],
                            format="png",
                            interactive=False,
                            elem_classes=["image-show-box"]
                        )
                        bgi_product_image_upload_zm = gr.File(
                            value=[],
                            label="商品正面",
                            file_count="multiple",
                            interactive=True,
                            file_types=["image"]
                        )
                        bgi_product_gallery_zm_add_btn = gr.Button(
                            "添加商品正面图片", min_width=200)
                        bgi_product_gallery_zm_remove_btn = gr.Button(
                            "清空", min_width=200)

                    bgi_product_gallery_zm_add_btn.click(fn=bgi_product_gallery_add_btn_click, inputs=[
                        bgi_product_gallery_zm, bgi_product_image_upload_zm], outputs=[bgi_product_gallery_zm, bgi_product_image_upload_zm])
                    bgi_product_gallery_zm_remove_btn.click(fn=bgi_product_gallery_remove_btn_click, inputs=[
                        bgi_product_gallery_zm, bgi_product_image_upload_zm], outputs=[bgi_product_gallery_zm, bgi_product_image_upload_zm])
                    with gr.Column(scale=1, min_width=200, elem_classes=["bgi_product_image_box"]):
                        bgi_product_gallery_bm = gr.Gallery(
                            label="商品背面",
                            height=200,
                            file_types=["image"],
                            format="png",
                            interactive=False,
                            elem_classes=["image-show-box"]
                        )
                        bgi_product_image_upload_bm = gr.File(
                            value=[],
                            label="商品背面",
                            file_count="multiple",
                            interactive=True,
                            file_types=["image"]
                        )
                        bgi_product_gallery_bm_add_btn = gr.Button("添加商品背面图片")
                        bgi_product_gallery_bm_remove_btn = gr.Button(
                            "清空", min_width=200)
                    bgi_product_gallery_bm_add_btn.click(fn=bgi_product_gallery_add_btn_click, inputs=[
                        bgi_product_gallery_bm, bgi_product_image_upload_bm], outputs=[bgi_product_gallery_bm, bgi_product_image_upload_bm])
                    bgi_product_gallery_bm_remove_btn.click(fn=bgi_product_gallery_remove_btn_click, inputs=[
                        bgi_product_gallery_bm, bgi_product_image_upload_bm], outputs=[bgi_product_gallery_bm, bgi_product_image_upload_bm])
                    with gr.Column(scale=1, min_width=200, elem_classes=["bgi_product_image_box"]):
                        bgi_product_gallery_sm = gr.Gallery(
                            label="商品上面",
                            height=200,
                            file_types=["image"],
                            format="png",
                            interactive=False,
                            elem_classes=["image-show-box"]
                        )
                        bgi_product_image_upload_sm = gr.File(
                            value=[],
                            label="商品上面",
                            file_count="multiple",
                            interactive=True,
                            file_types=["image"]
                        )
                        bgi_product_gallery_sm_add_btn = gr.Button("添加商品上面图片")
                        bgi_product_gallery_sm_remove_btn = gr.Button(
                            "清空", min_width=200)
                    bgi_product_gallery_sm_add_btn.click(fn=bgi_product_gallery_add_btn_click, inputs=[
                        bgi_product_gallery_sm, bgi_product_image_upload_sm], outputs=[bgi_product_gallery_sm, bgi_product_image_upload_sm])
                    bgi_product_gallery_sm_remove_btn.click(fn=bgi_product_gallery_remove_btn_click, inputs=[
                        bgi_product_gallery_sm, bgi_product_image_upload_sm], outputs=[bgi_product_gallery_sm, bgi_product_image_upload_sm])
                    with gr.Column(scale=1, min_width=200, elem_classes=["bgi_product_image_box"]):
                        bgi_product_gallery_xm = gr.Gallery(
                            label="商品下面",
                            height=200,
                            file_types=["image"],
                            format="png",
                            interactive=False,
                            elem_classes=["image-show-box"]
                        )
                        bgi_product_image_upload_xm = gr.File(
                            value=[],
                            label="商品下面",
                            file_count="multiple",
                            interactive=True,
                            file_types=["image"]
                        )
                        bgi_product_gallery_xm_add_btn = gr.Button("添加商品下面图片")
                        bgi_product_gallery_xm_remove_btn = gr.Button(
                            "清空", min_width=200)
                    bgi_product_gallery_xm_add_btn.click(fn=bgi_product_gallery_add_btn_click, inputs=[
                        bgi_product_gallery_xm, bgi_product_image_upload_xm], outputs=[bgi_product_gallery_xm, bgi_product_image_upload_xm])
                    bgi_product_gallery_xm_remove_btn.click(fn=bgi_product_gallery_remove_btn_click, inputs=[
                        bgi_product_gallery_xm, bgi_product_image_upload_xm], outputs=[bgi_product_gallery_xm, bgi_product_image_upload_xm])
                    with gr.Column(scale=1, min_width=200, elem_classes=["bgi_product_image_box"]):
                        bgi_product_gallery_lm = gr.Gallery(
                            label="商品左面",
                            height=200,
                            file_types=["image"],
                            format="png",
                            interactive=False,
                            elem_classes=["image-show-box"]
                        )
                        bgi_product_image_upload_lm = gr.File(
                            value=[],
                            label="商品左面",
                            file_count="multiple",
                            interactive=True,
                            file_types=["image"]
                        )
                        bgi_product_gallery_lm_add_btn = gr.Button("添加商品左面图片")
                        bgi_product_gallery_lm_remove_btn = gr.Button(
                            "清空", min_width=200)
                    bgi_product_gallery_lm_add_btn.click(fn=bgi_product_gallery_add_btn_click, inputs=[
                        bgi_product_gallery_lm, bgi_product_image_upload_lm], outputs=[bgi_product_gallery_lm, bgi_product_image_upload_lm])
                    bgi_product_gallery_lm_remove_btn.click(fn=bgi_product_gallery_remove_btn_click, inputs=[
                        bgi_product_gallery_lm, bgi_product_image_upload_lm], outputs=[bgi_product_gallery_lm, bgi_product_image_upload_lm])
                    with gr.Column(scale=1, min_width=200, elem_classes=["bgi_product_image_box"]):
                        bgi_product_gallery_rm = gr.Gallery(
                            label="商品右面",
                            height=200,
                            file_types=["image"],
                            format="png",
                            interactive=False,
                            elem_classes=["image-show-box"]
                        )
                        bgi_product_image_upload_rm = gr.File(
                            value=[],
                            label="商品右面",
                            file_count="multiple",
                            interactive=True,
                            file_types=["image"]
                        )
                        bgi_product_gallery_rm_add_btn = gr.Button("添加商品右面图片")
                        bgi_product_gallery_rm_remove_btn = gr.Button(
                            "清空", min_width=200)
                    bgi_product_gallery_rm_add_btn.click(fn=bgi_product_gallery_add_btn_click, inputs=[
                        bgi_product_gallery_rm, bgi_product_image_upload_rm], outputs=[bgi_product_gallery_rm, bgi_product_image_upload_rm])
                    bgi_product_gallery_rm_remove_btn.click(fn=bgi_product_gallery_remove_btn_click, inputs=[
                        bgi_product_gallery_rm, bgi_product_image_upload_rm], outputs=[bgi_product_gallery_rm, bgi_product_image_upload_rm])
                bgi_product_topic_input = gr.Textbox(
                    label="输入商品主题",
                    placeholder="如：华为nova14手机",
                    elem_classes=["game-description-input"],
                    interactive=True
                )
                bgi_modification_scope_select = gr.CheckboxGroup(
                    label="请选择改动范围",
                    choices=["产品视角", "商品背景", "深度生成产品多视角v1.0"],
                    value=[],
                    interactive=True
                )
                bgi_custom_requirements_input = gr.Textbox(
                    label="自定义需求，可不填，用/隔开",
                    placeholder="如：on the water/45 degree/warm color",
                    interactive=True
                )
                bgi_output_images_num_input = gr.Slider(
                    label="请输入生成条数",
                    minimum=1,
                    maximum=100,
                    interactive=True,
                    step=1,
                    value=1
                )
                bgi_submit_btn = gr.Button("提交任务")
        with gr.Row():
            bgi_result_gallery = gr.Gallery(
                label="生成结果",
                file_types=["image"],
                type="filepath",
                height=200,
                interactive=False
            )

    with gr.Tab("amazon/google play search"):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## google play")
                google_play_search_input = gr.Textbox(label="google play search",
                                                      placeholder="请输入google play搜索关键词", interactive=True)
                google_play_search_btn = gr.Button("search")
                google_play_search_result = gr.Dataframe(label="google play search result",
                                                         interactive=False)
            with gr.Column(scale=1):
                gr.Markdown("## amazon")
                amazon_search_input = gr.Textbox(label="amazon search",
                                                 placeholder="请输入amazon搜索关键词", interactive=True)
                amazon_search_btn = gr.Button("search")
                amazon_search_result = gr.Dataframe(label="amazon search result",
                                                    interactive=False)

    google_play_search_btn.click(fn=google_play_search, inputs=[
                                 google_play_search_input], outputs=[google_play_search_result])
    amazon_search_btn.click(fn=amazon_search, inputs=[
                            amazon_search_input], outputs=[amazon_search_result])

    m2v_v1_clear_btn_output = list(m2v_v1_group1_container_img)
    m2v_v1_clear_btn_output.extend(m2v_v1_group2_container_img)
    m2v_v1_clear_btn_output.extend(m2v_v1_group3_container_img)
    m2v_v1_clear_btn.click(fn=m2v_v1_clear, inputs=[m2v_v1_group_number, m2v_v1_group_img_container_number],
                           outputs=m2v_v1_clear_btn_output)

    m2v_v1_generate_input = [m2v_v1_positive_prompt, m2v_v1_negative_prompt]
    m2v_v1_generate_input.extend(m2v_v1_group1_container_img)
    m2v_v1_generate_input.extend(m2v_v1_group2_container_img)
    m2v_v1_generate_input.extend(m2v_v1_group3_container_img)
    m2v_v1_generate_btn.click(
        fn=m2v_v1_generate, inputs=(m2v_v1_generate_input),
        outputs=[m2v_v1_video1, m2v_v1_video2, m2v_v1_video3])
    # chatbot_history才是真正的历史信息
    ad_agent_user_input.submit(fn=user_input_func, inputs=[ad_agent_user_input, chatbot], outputs=[chatbot]).then(
        fn=send_message_to_art_ad_agent, inputs=[user_id, ad_agent_user_input, chatbot, user_material_id], outputs=[ad_agent_user_input, chatbot, ad_agent_material_library, user_material_id])
    # ad_agent_file_explorer.change(
    #     fn=change_file, inputs=[ad_agent_file_explorer], outputs=[video_display, image_display])

    demo.load(fn=load_app, inputs=[user_id], outputs=[user_id, chatbot])

    step1_submit_btn.click(fn=step1_submit, inputs=[user_id,
                                                    game_video_input, game_cover_input, game_description_input],
                           outputs=[game_video_input_width, game_video_input_height, img_v1_gallery, img_v1_gallery_select_box, all_img_v1_list])
    step2_submit_btn.click(fn=step2_submit, inputs=[
                           user_id, img_v1_gallery_select_box, all_img_v1_list], outputs=[all_video_v2_list, img_of_video_v2, img_of_video_v2_annotated, x_slider, y_slider, width_slider])
    step3_submit_btn.click(fn=step3_submit, inputs=[
                           user_id, all_video_v2_list, game_video_input, x_slider, y_slider, width_slider], outputs=[game_ad_video_final_output])

    x_slider.change(fn=update_game_ad_video_mid_state, inputs=[
                    x_slider, y_slider, width_slider, img_of_video_v2, game_video_input, game_video_input_width, game_video_input_height], outputs=[img_of_video_v2_annotated])

    y_slider.change(fn=update_game_ad_video_mid_state, inputs=[
                    x_slider, y_slider, width_slider, img_of_video_v2, game_video_input, game_video_input_width, game_video_input_height], outputs=[img_of_video_v2_annotated])

    width_slider.change(fn=update_game_ad_video_mid_state, inputs=[
        x_slider, y_slider, width_slider, img_of_video_v2, game_video_input, game_video_input_width, game_video_input_height], outputs=[img_of_video_v2_annotated])

    bgi_submit_btn.click(fn=bgi_submit, inputs=[
        bgi_product_gallery_zm, bgi_product_gallery_bm, bgi_product_gallery_sm, bgi_product_gallery_xm, bgi_product_gallery_lm, bgi_product_gallery_rm, bgi_product_topic_input, bgi_modification_scope_select, bgi_custom_requirements_input, bgi_output_images_num_input], outputs=[bgi_result_gallery])

demo.queue(max_size=20, default_concurrency_limit=5)
demo.launch(server_name="0.0.0.0", server_port=6003, share=False)
