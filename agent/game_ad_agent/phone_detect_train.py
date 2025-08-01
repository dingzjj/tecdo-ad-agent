from ultralytics import YOLO
from pathlib import Path

model = YOLO(Path("/data/dzj/ad_agent/agent/game_ad_agent/model/yolo11m.pt"))

results = model.train(
    data="/data/dzj/dataset/phone-detect/all_dir2/detect.yaml", epochs=100, batch=16)
    