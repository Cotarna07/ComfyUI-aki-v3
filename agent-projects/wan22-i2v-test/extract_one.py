import cv2, os, sys

path = sys.argv[1] if len(sys.argv) > 1 else r"D:\ComfyUI-aki-v3\ComfyUI\output\debug_nonturbo_00001_.mp4"
tag = os.path.splitext(os.path.basename(path))[0]
out_dir = r"D:\ComfyUI-aki-v3\agent-projects\wan22-i2v-test\frames"
os.makedirs(out_dir, exist_ok=True)

cap = cv2.VideoCapture(path)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
for label, idx in [("first", 0), ("mid", total//2), ("last", total-1)]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if ok:
        scale = 360 / frame.shape[1]
        small = cv2.resize(frame, (360, int(frame.shape[0]*scale)))
        dst = os.path.join(out_dir, f"{tag}_{label}{idx}.png")
        cv2.imwrite(dst, small)
        print(f"[OK] {label} frame{idx} -> {dst}")
cap.release()
print(f"total={total}")
