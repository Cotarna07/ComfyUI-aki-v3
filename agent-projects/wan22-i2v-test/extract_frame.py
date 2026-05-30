import cv2, os, sys

out_dir = r"D:\ComfyUI-aki-v3\agent-projects\wan22-i2v-test\frames"
os.makedirs(out_dir, exist_ok=True)

videos = {
    "cascade_turbo": r"D:\ComfyUI-aki-v3\ComfyUI\output\wan22_i2v_test_00001_.mp4",
    "single_20step": r"D:\ComfyUI-aki-v3\ComfyUI\output\debug_simple_00001_.mp4",
}

for tag, path in videos.items():
    if not os.path.exists(path):
        print(f"[SKIP] {tag}: not found")
        continue
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # 抽中间帧
    mid = total // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
    ok, frame = cap.read()
    if ok:
        # 缩小到宽度 320 方便查看
        scale = 320 / frame.shape[1]
        small = cv2.resize(frame, (320, int(frame.shape[0]*scale)))
        dst = os.path.join(out_dir, f"{tag}_frame{mid}.png")
        cv2.imwrite(dst, small)
        print(f"[OK] {tag}: {w}x{h}, {total}帧, 抽第{mid}帧 -> {dst}")
    else:
        print(f"[FAIL] {tag}: 读帧失败")
    cap.release()
