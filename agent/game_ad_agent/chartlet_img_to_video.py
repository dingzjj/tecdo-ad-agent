"""完全无头模式的视频分割函数（适用于服务器环境）"""

import cv2
from cv2.gapi.ot import TRACKED
import numpy as np
import os
import time
from ultralytics import YOLO
from deal_img import chartlet_img_with_mask
from phone_segment_predict_img import predict_img


def chartlet_img_to_video(model_path, input_video_path, output_video_path, chartlet_img_path, save_frames=False):
    """
    完全无头模式的视频分割函数（适用于服务器环境）

    Args:
        model_path: 模型文件路径
        input_video_path: 输入视频路径
        output_video_path: 输出视频路径
        conf_threshold: 置信度阈值
        save_frames: 是否保存关键帧
    """
    try:
        chartlet_img = cv2.imread(chartlet_img_path)
        # 检查文件是否存在
        if not os.path.exists(model_path):
            print(f"错误: 模型文件不存在: {model_path}")
            return

        if not os.path.exists(input_video_path):
            print(f"错误: 输入视频文件不存在: {input_video_path}")
            return

        # 确保输出目录存在
        output_dir = os.path.dirname(output_video_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        # 打开输入视频文件
        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            print("错误: 无法打开视频文件")
            return

        # 获取视频的基本信息
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"视频信息:")
        print(f"  分辨率: {frame_width}x{frame_height}")
        print(f"  FPS: {fps}")
        print(f"  总帧数: {total_frames}")
        print(f"  时长: {total_frames/fps:.2f} 秒")

        # 创建视频编写器以保存输出视频
        # 尝试多种编码器以确保兼容性
        fourcc_options = ['mp4v', 'avc1', 'XVID', 'MJPG']
        out = None

        for fourcc_code in fourcc_options:
            try:
                fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                out = cv2.VideoWriter(
                    output_video_path, fourcc, fps, (frame_width, frame_height))
                if out.isOpened():
                    print(f"使用编码器: {fourcc_code}")
                    break
                else:
                    out.release()
            except Exception as e:
                print(f"编码器 {fourcc_code} 失败: {e}")
                continue

        if out is None or not out.isOpened():
            print("错误: 无法创建输出视频文件，尝试使用默认编码器")
            # 如果所有编码器都失败，使用默认编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_video_path, fourcc,
                                  fps, (frame_width, frame_height))

            if not out.isOpened():
                print("错误: 无法创建输出视频文件")
                cap.release()
                return

        # 创建帧保存目录
        frames_dir = None
        if save_frames:
            # frames_dir根据output_video_path的父目录下
            frames_dir = output_video_path.replace('.mp4', '_frames')
            os.makedirs(frames_dir, exist_ok=True)
        # 处理统计
        frame_count = 0
        processed_count = 0
        start_time = time.time()
        # 逐帧处理视频
        while cap.isOpened():
            # frame为图片
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            try:
                # 使用模型对当前帧进行实例分割
                segment_result = predict_img(frame)

                # 方法一：透视变换
                # 将chartlet_img_path插入到frame中
                frame = chartlet_img_with_mask(
                    chartlet_img, frame, segment_result)

                # 方法二：局部重绘

                processed_count += 1

                # 保存关键帧（如果有检测结果）
                if save_frames:
                    frame_filename = os.path.join(
                        frames_dir, f"frame_{frame_count:06d}.jpg")
                    cv2.imwrite(frame_filename, frame)

                # 写入视频帧
                try:
                    out.write(frame)
                except Exception as write_error:
                    print(f"写入第 {frame_count} 帧时出错: {write_error}")
                    continue

                # 显示进度
                if frame_count % 30 == 0:  # 每30帧显示一次进度
                    progress = (frame_count / total_frames) * 100
                    elapsed_time = time.time() - start_time
                    fps_processed = frame_count / elapsed_time if elapsed_time > 0 else 0
                    print(f"进度: {progress:.1f}% ({frame_count}/{total_frames}) "
                          f"处理速度: {fps_processed:.1f} FPS")

            except Exception as e:
                print(f"处理第 {frame_count} 帧时出错: {e}")
                continue

        # 释放资源
        cap.release()
        out.release()

        # 显示最终统计
        total_time = time.time() - start_time
        print(f"\n处理完成!")
        print(f"  总处理时间: {total_time:.2f} 秒")
        print(f"  处理帧数: {processed_count}")
        print(f"  平均处理速度: {processed_count/total_time:.1f} FPS")
        print(f"  输出文件: {output_video_path}")

        # 验证输出文件
        if os.path.exists(output_video_path):
            file_size = os.path.getsize(output_video_path)
            print(f"  输出文件大小: {file_size / 1024 / 1024:.2f} MB")

            # 尝试读取输出视频验证
            try:
                test_cap = cv2.VideoCapture(output_video_path)
                if test_cap.isOpened():
                    test_fps = test_cap.get(cv2.CAP_PROP_FPS)
                    test_frames = int(test_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    test_width = int(test_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    test_height = int(test_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                    print(f"✅ 输出视频验证成功:")
                    print(f"   FPS: {test_fps}")
                    print(f"   帧数: {test_frames}")
                    print(f"   分辨率: {test_width}x{test_height}")

                    test_cap.release()
                else:
                    print("⚠️  输出视频无法读取，可能存在编码问题")
            except Exception as e:
                print(f"⚠️  验证输出视频时出错: {e}")
        else:
            print("❌ 输出文件未创建")

        if save_frames and frames_dir:
            print(f"  关键帧保存目录: {frames_dir}")

    except KeyboardInterrupt:
        print("\n用户中断处理")
        if 'cap' in locals():
            cap.release()
        if 'out' in locals():
            out.release()

    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        if 'cap' in locals():
            cap.release()
        if 'out' in locals():
            out.release()


# 示例调用
if __name__ == "__main__":
    model_path = "/data/dzj/yolov8-segment/runs/segment/train/weights/best.pt"
    input_video_path = "/data/dzj/yolov8-segment/data/video1.mp4"
    chartlet_img_path = "/data/dzj/yolov8-segment/data/phone.jpg"
    output_video_path = "/data/dzj/yolov8-segment/result/result3.mp4"
    # 完全无头模式处理
    # TODO 手机需要分为竖屏和横屏两种情况,增加手机+游戏画面

    chartlet_img_to_video(
        model_path=model_path,
        input_video_path=input_video_path,
        output_video_path=output_video_path,
        chartlet_img_path=chartlet_img_path,
        save_frames=True
    )
