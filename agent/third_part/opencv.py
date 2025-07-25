import os
import sys
import cv2
import numpy
from moviepy import editor
from agent.utils import temp_dir


class WatermarkRemover():

    def __init__(self, threshold: int, kernel_size: int, max_display_size: tuple):
        self.threshold = threshold  # 阈值分割所用阈值
        self.kernel_size = kernel_size  # 膨胀运算核尺寸
        # 最大显示尺寸 (width, height)，None表示自动检测
        self.max_display_size = max_display_size

    # 根据用户手动选择的ROI（Region of Interest，感兴趣区域）框选水印或字幕位置。
    def select_roi(self, img: numpy.ndarray, hint: str) -> list:
        '''
    框选水印或字幕位置，SPACE或ENTER键退出
    :param img: 显示图片
    :return: 框选区域坐标
    '''
        # 获取屏幕分辨率
        if self.max_display_size is not None:
            # 使用用户自定义的最大显示尺寸
            screen_width, screen_height = self.max_display_size
        else:
            # 自动检测屏幕分辨率
            try:
                import tkinter as tk
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
            except:
                # 如果无法获取屏幕分辨率，使用默认值
                screen_width = 1920
                screen_height = 1080

        # 计算合适的缩放比例，确保图片能完全显示在屏幕上
        # 留出一些边距，避免图片紧贴屏幕边缘
        margin = 100
        max_width = screen_width - margin
        max_height = screen_height - margin

        # 计算缩放比例
        width_ratio = max_width / img.shape[1]
        height_ratio = max_height / img.shape[0]
        scale_ratio = min(width_ratio, height_ratio, 1.0)  # 不超过原尺寸

        # 如果图片已经小于屏幕，使用原尺寸
        if scale_ratio >= 1.0:
            scale_ratio = 1.0

        # 计算缩放后的尺寸
        w, h = int(scale_ratio * img.shape[1]), int(scale_ratio * img.shape[0])
        resize_img = cv2.resize(img, (w, h))

        print(f"原图尺寸: {img.shape[1]}x{img.shape[0]}")
        print(f"缩放比例: {scale_ratio:.2f}")
        print(f"显示尺寸: {w}x{h}")
        print(f"屏幕尺寸: {screen_width}x{screen_height}")

        # 创建ROI选择窗口
        window_name = f"{hint} - 按SPACE或ENTER确认选择"
        roi = cv2.selectROI(window_name, resize_img, False, False)

        # 确保所有窗口都被正确关闭
        cv2.destroyAllWindows()
        cv2.waitKey(1)  # 给系统一点时间来关闭窗口

        # 将ROI坐标转换回原图坐标系
        watermark_roi = [int(roi[0] / scale_ratio), int(roi[1] / scale_ratio),
                         int(roi[2] / scale_ratio), int(roi[3] / scale_ratio)]
        return watermark_roi

    # 对输入的蒙版进行膨胀运算，扩大蒙版的范围

    def dilate_mask(self, mask: numpy.ndarray) -> numpy.ndarray:
        '''
    对蒙版进行膨胀运算
    :param mask: 蒙版图片
    :return: 膨胀处理后蒙版
    '''
        kernel = numpy.ones((self.kernel_size, self.kernel_size), numpy.uint8)
        mask = cv2.dilate(mask, kernel)
        return mask

    # 根据手动选择的ROI区域，在单帧图像中生成水印或字幕的蒙版。
    def generate_single_mask(self, img: numpy.ndarray, roi: list, threshold: int) -> numpy.ndarray:
        '''
    通过手动选择的ROI区域生成单帧图像的水印蒙版
    :param img: 单帧图像
    :param roi: 手动选择区域坐标
    :param threshold: 二值化阈值
    :return: 水印蒙版
    '''
        # 区域无效，程序退出
        if len(roi) != 4:
            print('NULL ROI!')
            sys.exit()

        # 复制单帧灰度图像ROI内像素点
        roi_img = numpy.zeros((img.shape[0], img.shape[1]), numpy.uint8)
        start_x, end_x = int(roi[1]), int(roi[1] + roi[3])
        start_y, end_y = int(roi[0]), int(roi[0] + roi[2])
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        roi_img[start_x:end_x, start_y:end_y] = gray[start_x:end_x, start_y:end_y]

        # 阈值分割
        _, mask = cv2.threshold(roi_img, threshold, 255, cv2.THRESH_BINARY)
        return mask

    # 通过截取视频中多帧图像生成多张水印蒙版，并通过逻辑与计算生成最终的水印蒙版
    def generate_watermark_mask(self, video_path: str, x, y, width, height) -> numpy.ndarray:
        '''
    截取视频中多帧图像生成多张水印蒙版，通过逻辑与计算生成最终水印蒙版
    :param video_path: 视频文件路径
    :return: 水印蒙版
    '''
        video = cv2.VideoCapture(video_path)
        success, frame = video.read()
        roi = [x, y, width, height]
        mask = numpy.ones((frame.shape[0], frame.shape[1]), numpy.uint8)
        mask.fill(255)
        step = video.get(cv2.CAP_PROP_FRAME_COUNT) // 5
        index = 0
        while success:
            if index % step == 0:
                mask = cv2.bitwise_and(
                    mask, self.generate_single_mask(frame, roi, self.threshold))
            success, frame = video.read()
            index += 1
        video.release()

        return self.dilate_mask(mask)

    # 根据手动选择的ROI区域，在单帧图像中生成字幕的蒙版。
    def generate_subtitle_mask(self, frame: numpy.ndarray, roi: list) -> numpy.ndarray:
        '''
    通过手动选择ROI区域生成单帧图像字幕蒙版
    :param frame: 单帧图像
    :param roi: 手动选择区域坐标
    :return: 字幕蒙版
    '''
        mask = self.generate_single_mask(
            # 仅使用ROI横坐标区域
            frame, [0, roi[1], frame.shape[1], roi[3]], self.threshold)
        return self.dilate_mask(mask)

    def inpaint_image(self, img: numpy.ndarray, mask: numpy.ndarray) -> numpy.ndarray:
        '''
    修复图像
    :param img: 单帧图像
    :parma mask: 蒙版
    :return: 修复后图像
    '''
        telea = cv2.inpaint(img, mask, 1, cv2.INPAINT_TELEA)
        return telea

    def merge_audio(self, input_path: str, output_path: str, temp_path: str):
        '''
    合并音频与处理后视频
    :param input_path: 原视频文件路径
    :param output_path: 封装音视频后文件路径
    :param temp_path: 无声视频文件路径
    '''
        with editor.VideoFileClip(input_path) as video:
            audio = video.audio
            with editor.VideoFileClip(temp_path) as opencv_video:
                clip = opencv_video.set_audio(audio)
                clip.to_videofile(output_path)

    def remove_video_watermark(self, src_video_path, desc_video_path, x, y, width, height):
        '''
    去除视频水印
    :param src_video_path: 原视频文件路径
    :param desc_video_path: 处理后视频文件路径
    :param x: 水印左上角x坐标
    :param y: 水印左上角y坐标
    :param width: 水印宽度
    :param height: 水印高度
    '''
        with temp_dir() as temp_dir_path:
            # 生成水印蒙版
            mask = self.generate_watermark_mask(
                src_video_path, x, y, width, height)

            # 创建待写入文件对象
            video = cv2.VideoCapture(src_video_path)
            fps = video.get(cv2.CAP_PROP_FPS)
            size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            video_writer = cv2.VideoWriter(
                # VideoWriter_fourcc
                temp_dir_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, size)

            # 逐帧处理图像
            success, frame = video.read()

            while success:
                frame = self.inpaint_image(frame, mask)
                video_writer.write(frame)
                success, frame = video.read()

            video.release()
            video_writer.release()

            # 封装视频
            self.merge_audio(src_video_path, desc_video_path, temp_dir_path)
