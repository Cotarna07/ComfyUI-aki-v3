from ultralytics import YOLO

model = YOLO('best.pt')
data_path = 'data.yaml'

results = model.train(
    data=data_path,
    epochs=500,
    batch=4,
    imgsz=640,
    project="./results",  # Основная директория
    name="medium",        # Поддиректория для эксперимента
    device="cuda",
    workers=1,
    verbose=True,

    # Цветовые аугментации
    hsv_h=0.015,      # Небольшое изменение оттенка
    hsv_s=0.4,        # Изменение насыщенности
    hsv_v=0.3,        # Изменение яркости

    # Геометрические трансформации
    degrees=1.0,      # Вращение (±1 градусов)
    translate=0.01,   # Сдвиг (1% от размера)
    scale=0.3,        # Масштабирование (70%-130%)

    # Отражения
    fliplr=0.4,       # Горизонтальное отражение (40% вероятность)
    flipud=0.05,      # Вертикальное отражение редко (5%)

    # Комплексные аугментации
    mosaic=0.7,       # Мозаика (70% вероятность)

    # Дополнительные аугментации
    erasing=0.2      # Random erasing (20% вероятность)
)