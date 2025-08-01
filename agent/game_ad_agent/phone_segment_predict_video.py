"""完全无头模式的视频分割函数（适用于服务器环境）"""

import cv2
import numpy as np
import os
import time
from ultralytics import YOLO


def segment_video_headless(model_path, input_video_path, output_video_path,
                           conf_threshold=0.8, save_frames=False):
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

        # 加载预训练的 YOLOv8 模型
        print(f"正在加载模型: {model_path}")
        model = YOLO(model_path)
        print("模型加载成功!")

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
            frames_dir = output_video_path.replace('.mp4', '_frames')
            os.makedirs(frames_dir, exist_ok=True)
            print(f"关键帧将保存到: {frames_dir}")

        # 处理统计
        frame_count = 0
        processed_count = 0
        start_time = time.time()

        print("开始处理视频...")

        # 逐帧处理视频
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            try:
                # 使用模型对当前帧进行实例分割
                results = model(frame, conf=conf_threshold, verbose=False)

                # 处理分割结果
                if results and len(results) > 0:
                    result = results[0]  # 获取第一个结果

                    # 检查是否有检测结果
                    if result.boxes is not None and len(result.boxes) > 0:
                        # 处理每个检测结果
                        for i in range(len(result.boxes)):
                            # 获取边界框信息
                            box = result.boxes[i]
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            conf = float(box.conf[0])
                            cls = int(box.cls[0])

                            # 获取类别名称
                            class_name = result.names[cls] if cls in result.names else f"Class_{
                                cls}"

                            # 绘制边界框
                            color = (0, 255, 0)  # 绿色
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                            # 绘制标签
                            label = f"{class_name} {conf:.2f}"
                            label_size = cv2.getTextSize(
                                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                            cv2.rectangle(frame, (x1, y1-label_size[1]-10),
                                          (x1+label_size[0], y1), color, -1)
                            cv2.putText(frame, label, (x1, y1-5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                            # 处理分割掩码
                            if result.masks is not None and i < len(result.masks):
                                mask = result.masks[i]
                                if mask is not None:
                                    try:
                                        # 将掩码转换为numpy数组
                                        mask_array = mask.data.cpu().numpy()
                                        if len(mask_array.shape) == 3:
                                            # 取第一个通道
                                            mask_array = mask_array[0]

                                        # 检查掩码尺寸
                                        mask_height, mask_width = mask_array.shape
                                        if mask_height != frame_height or mask_width != frame_width:
                                            # 将掩码调整到原始图像尺寸
                                            mask_array = cv2.resize(
                                                mask_array, (frame_width, frame_height))

                                        # 确保掩码值在0-1范围内
                                        mask_array = np.clip(mask_array, 0, 1)

                                        # 创建彩色掩码
                                        colored_mask = np.zeros_like(frame)
                                        mask_bool = mask_array > 0.5  # 使用阈值创建布尔掩码
                                        colored_mask[mask_bool] = color

                                        # 应用掩码到图像（半透明）
                                        alpha = 0.3
                                        frame = cv2.addWeighted(
                                            frame, 1-alpha, colored_mask, alpha, 0)

                                    except Exception as mask_error:
                                        print(f"处理掩码时出错: {mask_error}")
                                        # 如果掩码处理失败，只绘制边界框
                                        continue

                processed_count += 1

                # 保存关键帧（如果有检测结果）
                if save_frames and results and len(results) > 0 and result.boxes is not None and len(result.boxes) > 0:
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


def segment_video_batch_headless(model_path, input_videos, output_dir, **kwargs):
    """
    完全无头模式的批量处理视频

    Args:
        model_path: 模型文件路径
        input_videos: 输入视频路径列表
        output_dir: 输出目录
        **kwargs: 其他参数传递给segment_video_headless函数
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, video_path in enumerate(input_videos):
        if os.path.exists(video_path):
            print(f"\n处理视频 {i+1}/{len(input_videos)}: {video_path}")

            # 生成输出文件名
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(
                output_dir, f"{video_name}_segmented.mp4")

            # 处理视频
            segment_video_headless(
                model_path, video_path, output_path, **kwargs)
        else:
            print(f"视频文件不存在: {video_path}")


# 示例调用
if __name__ == "__main__":
    model_path = "/data/dzj/yolov8-segment/runs/segment/train/weights/best.pt"
    input_video_path = "/data/dzj/yolov8-segment/data/video2.mp4"
    output_video_path = "/data/dzj/yolov8-segment/result/result1.mp4"
    # 完全无头模式处理
    segment_video_headless(
        model_path=model_path,
        input_video_path=input_video_path,
        output_video_path=output_video_path,
        conf_threshold=0.8,
        save_frames=True
    )
