from agent.utils import get_time_id
import cv2
from PIL import Image
from config import conf
import os
import gradio as gr
from agent.game_ad_agent.generate_img import generate_image_prompt,generate_image_v1
from agent.game_ad_agent.game_ad_workfow import chartlet_phone_and_game
import cv2
from agent.third_part.i2v import Veo3
from agent.game_ad_agent.generate_video import generate_video_prompt
from agent.game_ad_agent.game_ad_workfow import get_video_first_frame
from agent.third_part.video_effects import video_stitching,VideoTransitionType
from agent.game_ad_agent.game_ad_workfow import chartlet_video_to_video

def step1_submit(user_id,game_video_input, game_cover,game_description):
    # 检查输入文件是否存在
    if not game_video_input or not os.path.exists(game_video_input):
        raise ValueError(f"视频文件不存在: {game_video_input}")

    # 获得game_video_input视频的宽高
    cap = cv2.VideoCapture(game_video_input)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {game_video_input}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    # 生成image v1
    image_prompt_list = generate_image_prompt(game_video_input,game_description)
    image_v1_dir = conf.get_path("user_data_dir") + f"/{user_id}/image_v1"
    os.makedirs(image_v1_dir, exist_ok=True)
    image_v1_list = []
    all_img_v1_list = {}
    image_v1_gallery_select_box = []
    for idx,image_prompt in enumerate(image_prompt_list):
        image_v1 = generate_image_v1(image_prompt)
        image_v1_content = chartlet_phone_and_game(cv2.imread(game_cover),image_v1)
        # 对image_v1进行游戏画面放置
        image_v1_path = f"{image_v1_dir}/{idx}.jpg"
        all_img_v1_list[idx] = {"image_prompt":image_prompt,"image_v1_path":image_v1_path}
        # 将其保存到user_id目录下
        cv2.imwrite(image_v1_path, image_v1_content)
        image_v1_list.append(image_v1_path)
        image_v1_gallery_select_box.append(f"{idx+1}")

    # 生成视频
    # 返回实际的视频文件路径
    return width, height,image_v1_list,gr.update(choices=image_v1_gallery_select_box),all_img_v1_list

def step2_submit(user_id,img_v1_gallery_select_box,all_img_v1_list):
    """
    提交,生成video v2
    img_v1_gallery_select_box返回的是index
    """

    all_video_v2_list = []
    output_dir = conf.get_path("user_data_dir") + f"/{user_id}/video_v2"
    for img_v1_index in img_v1_gallery_select_box:
        img_v1_index=int(img_v1_index)
        # {"image_prompt":image_prompt,"image_v1_path":image_v1_path}
        img_v1 = all_img_v1_list[img_v1_index-1]
        img_v1_path = img_v1["image_v1_path"]
        print(f"img_v1: {img_v1}")
        video_prompt = generate_video_prompt(img_v1_path,img_v1["image_prompt"])
        print(f"video_prompt: {video_prompt}")
        generator = Veo3(
            project_id="ca-biz-vypngh-y97n",  # 项目ID
            output_dir=output_dir   # 视频保存目录
        )
        video_path = generator.generate_video(video_prompt,img_v1_path)
        # 将video_path重命名为idx.mp4
        os.rename(video_path,os.path.join(output_dir,f"{img_v1_index}.mp4"))
        video_path = os.path.join(output_dir,f"{img_v1_index}.mp4")
        all_video_v2_list.append(video_path)
    
    img_of_video_v2 = get_video_first_frame(cv2.VideoCapture(all_video_v2_list[0]))
    img_of_video_v2_path = os.path.join(conf.get_path("temp_dir"),f"{get_time_id()}.png")
    cv2.imwrite(img_of_video_v2_path,img_of_video_v2)
    # outputs=[all_video_v2_list, img_of_video_v2, img_of_video_v2_annotated, x_slider, y_slider, width_slider
    return all_video_v2_list,img_of_video_v2_path,(img_of_video_v2_path, []),gr.update(maximum=img_of_video_v2.shape[1]),gr.update(maximum=img_of_video_v2.shape[0]),gr.update(maximum=img_of_video_v2.shape[1])

def step3_submit(user_id,all_video_v2_list,game_video_input,x,y,width):

    """
    提交,生成最终视频
    """
    x1= x
    y1 = y
    # 先将视频进行拼接
    video_stitching_temp_path = os.path.join(conf.get_path("temp_dir"),f"{get_time_id()}")
    video_stitching_path = video_stitching(video_stitching_temp_path,all_video_v2_list,VideoTransitionType.CONCATENATE)
    # 将视频进行chartlet
    main_cap = cv2.VideoCapture(video_stitching_path)
    overlay_cap = cv2.VideoCapture(game_video_input)
    # 1.获得overlay_cap的宽高
    overlay_width = int(overlay_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    overlay_height = int(overlay_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # 2.获得main_cap的宽高
    main_width = int(main_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    main_height = int(main_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # 3.x1+width,y1+height，来控制chartlet的宽高，假如有一边超过main_cap的宽高，则进行收缩，并且保持宽高比，直到两边都小于main_cap的宽高
    x2 = x1+width
    y2 = y1+width*(overlay_height/overlay_width)
    # 保持宽高比
    if x2>main_width:
        x2 = main_width
        y2 = y1+(x2-x1)*(overlay_height/overlay_width)
    if y2>main_height:
        y2 = main_height
        x2 = x1+(y2-y1)*(overlay_width/overlay_height)
    x2 = int(x2)
    y2 = int(y2)
    final_video_path = conf.get_path("user_data_dir") + f"/{user_id}/final_video.mp4"
    chartlet_video_to_video(main_cap,overlay_cap,(x1,y1,x2,y2),final_video_path)
    return final_video_path
def get_game_ad_video_mid_state(game_ad_video_mid_output):
    print(f"game_ad_video_mid_output: {game_ad_video_mid_output}")
    """
    获得中间状态
    """
    # 处理Gradio组件传递的参数
    # game_ad_video_mid_output 可能是元组 (image_path, annotations) 或者直接是路径
    if isinstance(game_ad_video_mid_output, tuple):
        video_path = game_ad_video_mid_output[0]  # 取第一个元素作为路径
    else:
        video_path = game_ad_video_mid_output

    # 检查输入文件是否存在
    if not video_path or not os.path.exists(video_path):
        raise ValueError(f"视频文件不存在: {video_path}")

    # 取出视频的第一张作为图片
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {video_path}")

    ret, frame = cap.read()
    cap.release()

    # 检查是否成功读取帧
    if not ret or frame is None:
        raise ValueError(f"无法从视频中读取帧: {video_path}")

    # 确保temp目录存在
    temp_dir = conf.get_path("temp_dir")
    os.makedirs(temp_dir, exist_ok=True)

    img_name = str(get_time_id()) + ".png"
    img_path = os.path.join(temp_dir, img_name)

    # 保存图片
    success = cv2.imwrite(img_path, frame)
    if not success:
        raise ValueError(f"无法保存图片到: {img_path}")

    # 获取图片的宽高
    height, width = frame.shape[:2]
    # 返回图片路径，x，y，width
    print(f"img_path: {img_path}")
    return img_path, gr.update(maximum=width), gr.update(maximum=height), gr.update(maximum=width)


def update_game_ad_video_mid_state(x_slider, y_slider, width_slider, game_ad_agent_mid_video_first_image, game_video_input, game_video_input_width, game_video_input_height):
    """
    更新中间状态
    """
    if x_slider > 0 and y_slider > 0 and width_slider > 0:
        if game_video_input_width == 0 or game_video_input_height == 0:
            # 通过game_video_input获得宽高
            cap = cv2.VideoCapture(game_video_input)
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {game_video_input}")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            game_video_input_width = width
            game_video_input_height = height
        x1 = x_slider
        y1 = y_slider
        x2 = int(x1 + width_slider)
        y2 = int(y1 + width_slider *
                 (game_video_input_height/game_video_input_width))
        return (game_ad_agent_mid_video_first_image, [((x1, y1, x2, y2), "")])
    else:
        return (game_ad_agent_mid_video_first_image, [])





    