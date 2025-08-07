import gradio as gr


def bgi_product_gallery_add_btn_click(bgi_product_gallery, bgi_product_image_input):
    if bgi_product_image_input is None:
        return bgi_product_gallery, gr.update(value=None)
    if bgi_product_gallery is not None:
        bgi_product_gallery.append(bgi_product_image_input)
        return bgi_product_gallery, gr.update(value=None)
    else:
        return [bgi_product_image_input], gr.update(value=None)


def bgi_product_gallery_remove_btn_click(bgi_product_gallery, bgi_product_image_input):
    return None, None

    