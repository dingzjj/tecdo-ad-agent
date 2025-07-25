from config import conf
import os
import cv2
import glob
import torch
import numpy as np
from tqdm import tqdm
from omegaconf import OmegaConf

# from vbench.utils import load_dimension_info

from agent.third_part.amt.utils.utils import (
    img2tensor, tensor2img,
    check_dim_and_resize
)
from agent.third_part.amt.utils.build_utils import build_from_cfg
from agent.third_part.amt.utils.utils import InputPadder


class FrameProcess:
    def __init__(self):
        pass

# 从视频路径中读取视频并将其转换为 RGB 格式的帧。
    def get_frames(self, video_path):
        frame_list = []
        video = cv2.VideoCapture(video_path)
        while video.isOpened():
            success, frame = video.read()
            if success:
                frame = cv2.cvtColor(
                    frame, cv2.COLOR_BGR2RGB)  # convert to rgb
                frame_list.append(frame)
            else:
                break
        video.release()
        assert frame_list != []
        return frame_list
# 从图像文件夹中读取图片，将其转换为 RGB 格式的帧。

    def get_frames_from_img_folder(self, img_folder):
        exts = ['jpg', 'png', 'jpeg', 'bmp', 'tif',
                'tiff', 'JPG', 'PNG', 'JPEG', 'BMP',
                'TIF', 'TIFF']
        frame_list = []
        imgs = sorted([p for p in glob.glob(os.path.join(
            img_folder, "*")) if os.path.splitext(p)[1][1:] in exts])
        # imgs = sorted(glob.glob(os.path.join(img_folder, "*.png")))
        for img in imgs:
            frame = cv2.imread(img, cv2.IMREAD_COLOR)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_list.append(frame)
        assert frame_list != []
        return frame_list
# 从帧列表中提取特定的帧，默认每隔一帧提取一次。

    def extract_frame(self, frame_list, start_from=0):
        extract = []
        for i in range(start_from, len(frame_list), 2):
            extract.append(frame_list[i])
        return extract


class MotionSmoothness:
    def __init__(self, config, ckpt, device):
        self.device = device
        self.config = config
        self.ckpt = ckpt
        self.niters = 1
        self.initialization()
        self.load_model()
    """
    加载模型：从配置文件和 checkpoint 文件中加载模型。
    使用 OmegaConf 加载网络配置文件。
    通过 build_from_cfg 函数构建模型。
    加载训练好的模型权重到 GPU 或 CPU。
    """

    def load_model(self):
        cfg_path = self.config
        ckpt_path = self.ckpt
        network_cfg = OmegaConf.load(cfg_path).network
        network_name = network_cfg.name
        print(f'Loading [{network_name}] from [{ckpt_path}]...')
        self.model = build_from_cfg(network_cfg)
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        self.model.load_state_dict(ckpt['state_dict'])
        self.model = self.model.to(self.device)
        self.model.eval()

    def initialization(self):
        if self.device == 'cuda':
            self.anchor_resolution = 1024 * 512
            self.anchor_memory = 1500 * 1024**2
            self.anchor_memory_bias = 2500 * 1024**2
            self.vram_avail = torch.cuda.get_device_properties(
                self.device).total_memory
            print("VRAM available: {:.1f} MB".format(
                self.vram_avail / 1024 ** 2))
        else:
            # Do not resize in cpu mode
            self.anchor_resolution = 8192*8192
            self.anchor_memory = 1
            self.anchor_memory_bias = 0
            self.vram_avail = 1

        self.embt = torch.tensor(1/2).float().view(1, 1, 1, 1).to(self.device)
        self.fp = FrameProcess()
# 计算运动平滑度

    def motion_score(self, video_path):
        iters = int(self.niters)
        # get inputs
        if video_path.endswith('.mp4'):
            frames = self.fp.get_frames(video_path)
        elif os.path.isdir(video_path):
            frames = self.fp.get_frames_from_img_folder(video_path)
        else:
            raise NotImplementedError
# 根据视频路径（.mp4 或图像文件夹）读取视频或图像帧。
        frame_list = self.fp.extract_frame(frames, start_from=0)
        # print(f'Loading [images] from [{video_path}], the number of images = [{len(frame_list)}]')
        inputs = [img2tensor(frame).to(self.device) for frame in frame_list]
        assert len(
            inputs) > 1, f"The number of input should be more than one (current {len(inputs)})"
        inputs = check_dim_and_resize(inputs)
        h, w = inputs[0].shape[-2:]

        scale = self.anchor_resolution / \
            (h * w) * np.sqrt((self.vram_avail -
                               self.anchor_memory_bias) / self.anchor_memory)
        scale = 1 if scale > 1 else scale
        scale = 1 / np.floor(1 / np.sqrt(scale) * 16) * 16
        if scale < 1:
            print(
                f"Due to the limited VRAM, the video will be scaled by {scale:.2f}")
        padding = int(16 / scale)
        padder = InputPadder(inputs[0].shape, padding)
        inputs = padder.pad(*inputs)

        # -----------------------  Interpolater -----------------------
        # print(f'Start frame interpolation:')
        for i in range(iters):
            # print(f'Iter {i+1}. input_frames={len(inputs)} output_frames={2*len(inputs)-1}')
            outputs = [inputs[0]]
            for in_0, in_1 in zip(inputs[:-1], inputs[1:]):
                in_0 = in_0.to(self.device)
                in_1 = in_1.to(self.device)
                with torch.no_grad():
                    imgt_pred = self.model(in_0, in_1, self.embt, scale_factor=scale, eval=True)[
                        'imgt_pred']
                outputs += [imgt_pred.cpu(), in_1.cpu()]
            inputs = outputs

        # -----------------------  cal_vfi_score -----------------------
        outputs = padder.unpad(*outputs)
        outputs = [tensor2img(out) for out in outputs]
        vfi_score = self.vfi_score(frames, outputs)
        norm = (255.0 - vfi_score)/255.0
        return norm
# 通过计算原始帧与插值帧之间的差异来衡量运动平滑度，使用均值绝对差异来计算

    def vfi_score(self, ori_frames, interpolate_frames):
        ori = self.fp.extract_frame(ori_frames, start_from=1)
        interpolate = self.fp.extract_frame(interpolate_frames, start_from=1)
        scores = []
        for i in range(len(interpolate)):
            scores.append(self.get_diff(ori[i], interpolate[i]))
        return np.mean(np.array(scores))
# 计算两帧之间的差异，具体为每个像素的绝对差值并求平均。

    def get_diff(self, img1, img2):
        img = cv2.absdiff(img1, img2)
        return np.mean(img)


def motion_smoothness(motion, video_list):
    sim = []
    video_results = []
    for video_path in tqdm(video_list):
        score_per_video = motion.motion_score(video_path)
        video_results.append(
            {'video_path': video_path, 'video_results': score_per_video})
        sim.append(score_per_video)
    avg_score = np.mean(sim)
    return avg_score, video_results


def compute_motion_smoothness(video_path):
    config = conf.get_path("amt_s_yaml")
    ckpt = conf.get_path("amt_s_pth")  # pretrained/amt_model/amt-s.pth
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    motion = MotionSmoothness(config, ckpt, device)
    all_results, video_results = motion_smoothness(motion, [video_path])
    # all_results = sum([d['video_results']
    #                    for d in video_results]) / len(video_results)
    # if get_world_size() > 1:
    #     video_results = gather_list_of_dict(video_results)

    return all_results, video_results
