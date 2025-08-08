import asyncio
import math
import random
from agent.e_commerce_agent.generate_multi_images import generate_multi_images_v1
import gradio as gr


def bgi_product_gallery_add_btn_click(bgi_product_gallery, bgi_product_image_upload):
    print(bgi_product_image_upload)
    if bgi_product_image_upload is None:
        return bgi_product_gallery, gr.update(value=None)
    if bgi_product_gallery is not None:
        bgi_product_gallery.extend(bgi_product_image_upload)
        return bgi_product_gallery, gr.update(value=None)
    else:
        return bgi_product_image_upload, gr.update(value=None)


def bgi_product_gallery_remove_btn_click(bgi_product_gallery, bgi_product_image_upload):
    return None, None


def bgi_submit(bgi_product_gallery_zm, bgi_product_gallery_bm, bgi_product_gallery_sm, bgi_product_gallery_xm, bgi_product_gallery_lm, bgi_product_gallery_rm, bgi_product_topic_input, bgi_modification_scope_select, bgi_custom_requirements_input, bgi_output_images_num_input):

    # 根据bgi_modification_scope_select的不同选项，启动不同功能
    all_image_path = []
    if bgi_product_gallery_zm is not None:
        all_image_path.extend(bgi_product_gallery_zm)
    if bgi_product_gallery_bm is not None:
        all_image_path.extend(bgi_product_gallery_bm)
    if bgi_product_gallery_sm is not None:
        all_image_path.extend(bgi_product_gallery_sm)
    if bgi_product_gallery_xm is not None:
        all_image_path.extend(bgi_product_gallery_xm)
    if bgi_product_gallery_lm is not None:
        all_image_path.extend(bgi_product_gallery_lm)
    if bgi_product_gallery_rm is not None:
        all_image_path.extend(bgi_product_gallery_rm)
    all_image_path = [image_path[0] for image_path in all_image_path]
    if len(all_image_path) == 0 or len(bgi_modification_scope_select) == 0:
        return None
    print(all_image_path)
    results = []
    # all_output_images_num表示总数
    all_output_images_num = int(bgi_output_images_num_input)
    one_output_images_num = math.ceil(
        all_output_images_num/len(all_image_path))
    for image_path in all_image_path:
        # 下面的生成不断消耗总数，进行随机生成
        now_results = asyncio.run(generate_multi_images_v1(
            image_path, bgi_product_topic_input, ','.join(bgi_modification_scope_select), bgi_custom_requirements_input, one_output_images_num))
        for result in now_results:
            results.append((result["image_path"], result["prompt"]))
    return results
