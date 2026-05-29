from ultralytics import YOLO
import torch

# Очистка памяти GPU перед запуском
torch.cuda.empty_cache()

# Загрузка вашей обученной модели
from ultralytics import YOLO

model = YOLO('results/nano/weights/best.pt')

results = model.predict(
    source="img.png",
    imgsz=640,
    conf=0.8,
    device=0,
    half=True,
    save=True,
    project="inference",
    name="final_run",
    exist_ok=True
)

torch.cuda.empty_cache()
