from ultralytics import YOLO

model = YOLO("yolo11m-seg.pt", task="segment")
results = model.train(
    data="/data/dzj/dataset/phone-segment/segment.yaml", epochs=100, batch=16)
    