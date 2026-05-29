"""
批量关闭 TEST 目录下所有工作流中的 PathchSageAttentionKJ / CheckpointLoaderKJ / DiffusionModelLoaderKJ 的 sage_attention 参数。
将这些节点的 sage_attention 设置为 "disabled"。
"""
import json
import os
import sys

TEST_DIR = r"D:\ComfyUI-aki-v3\agent-skills\comfyui\workflows\TEST"

# KJNodes 中包含 sage_attention 参数的节点类型
TARGET_TYPES = {
    "PathchSageAttentionKJ",
    "CheckpointLoaderKJ",
    "DiffusionModelLoaderKJ",
}

def fix_node(node):
    """修改节点的 sage_attention widget 值为 'disabled'"""
    node_type = node.get("type", "")
    if node_type not in TARGET_TYPES:
        return False

    widgets_values = node.get("widgets_values")
    if not widgets_values:
        return False

    # widgets_values 是一个数组，sage_attention 通常是第一个元素
    # 但也可能通过 inputs 中的 widget 指定
    modified = False

    # 方式 1: 通过 inputs 找到 sage_attention widget 的名称和值
    for inp in node.get("inputs", []):
        w = inp.get("widget", {})
        if w.get("name") == "sage_attention":
            current = inp.get("widget", {}).get("value")
            # 其实值是存储在 widgets_values 中的

    # 实际情况：widgets_values 数组的第一个元素就是 sage_attention 的值
    # 顺序与 inputs 中的 widget 定义一致
    # PathchSageAttentionKJ: [sage_attention, allow_compile]
    # CheckpointLoaderKJ: [ckpt_name, weight_dtype, compute_dtype, patch_cublaslinear, sage_attention, enable_fp16_accumulation]
    # DiffusionModelLoaderKJ: [model_name, weight_dtype, compute_dtype, patch_cublaslinear, sage_attention, enable_fp16_accumulation]

    # 找出 sage_attention 在 widgets_values 中的索引
    # 注意：只有带 widget 的 input 才对应 widgets_values 中的位置
    sage_idx = None
    widget_idx = 0
    for inp in node.get("inputs", []):
        w = inp.get("widget", {})
        if w:  # 只有带 widget 的 input 才算
            name = w.get("name", "")
            if name == "sage_attention":
                sage_idx = widget_idx
            widget_idx += 1

    if sage_idx is not None and sage_idx < len(widgets_values):
        old_val = widgets_values[sage_idx]
        if old_val != "disabled":
            widgets_values[sage_idx] = "disabled"
            print(f"  [{node_type}] id={node.get('id','?')}: sage_attention {old_val!r} -> 'disabled'")
            modified = True
    else:
        # 回退：检查 inputs 中的 widget value
        for inp in node.get("inputs", []):
            w = inp.get("widget", {})
            if w.get("name") == "sage_attention":
                old_val = w.get("value", None)
                if old_val is not None and old_val != "disabled":
                    w["value"] = "disabled"
                    print(f"  [{node_type}] id={node.get('id','?')}: sage_attention (input) {old_val!r} -> 'disabled'")
                    modified = True

    # 额外：检查 widgets_values 中的字符串值是否为 "auto" 或 true（布尔）
    # 这是针对旧格式的兜底
    if not modified and widgets_values:
        for i, val in enumerate(widgets_values):
            if isinstance(val, str) and val in ("auto", "sageattn", "sageattn_qk_int8_pv_fp16_cuda",
                                                  "sageattn_qk_int8_pv_fp16_triton",
                                                  "sageattn_qk_int8_pv_fp8_cuda",
                                                  "sageattn_qk_int8_pv_fp8_cuda++",
                                                  "sageattn3", "sageattn3_per_block_mean"):
                # 确认这是 sage_attention 参数（不是 ckpt_name 之类的）
                if sage_idx is None and node_type == "PathchSageAttentionKJ" and i == 0:
                    widgets_values[i] = "disabled"
                    print(f"  [{node_type}] id={node.get('id','?')}: widgets_values[0] {val!r} -> 'disabled' (heuristic)")
                    modified = True

    # PathchSageAttentionKJ 兜底：如果以上都没匹配到，且 widgets_values[0] 是有效 sageattn 模式
    if not modified and node_type == "PathchSageAttentionKJ" and widgets_values and len(widgets_values) >= 1:
        v0 = widgets_values[0]
        if v0 != "disabled":
            widgets_values[0] = "disabled"
            print(f"  [{node_type}] id={node.get('id','?')}: widgets_values[0] {v0!r} -> 'disabled' (fallback)")
            modified = True

    return modified


def collect_all_nodes(data):
    """递归收集所有节点（包括 definitions.subgraphs 中的嵌套节点）"""
    nodes = list(data.get("nodes", []))
    # 处理 definitions.subgraphs
    for subgraph in data.get("definitions", {}).get("subgraphs", []):
        nodes.extend(subgraph.get("nodes", []))
    # 处理 groups 中的嵌套节点
    for group in data.get("groups", []):
        if isinstance(group, dict):
            nodes.extend(group.get("nodes", []))
    return nodes


def process_file(filepath):
    rel = os.path.relpath(filepath, TEST_DIR)
    print(f"\n处理: {rel}")

    try:
        # 先尝试 utf-8-sig 处理 BOM 文件
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  -> 跳过: JSON 解析失败 ({e})")
        return

    modified_count = 0
    nodes = collect_all_nodes(data)
    for node in nodes:
        if fix_node(node):
            modified_count += 1

    if modified_count > 0:
        # 使用 UTF-8 无 BOM 写回
        content = json.dumps(data, indent="\t", ensure_ascii=False)
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"  -> 已保存，共修改 {modified_count} 个节点")
    else:
        print(f"  -> 无需修改")


def main():
    if not os.path.isdir(TEST_DIR):
        print(f"错误: 目录不存在: {TEST_DIR}")
        sys.exit(1)

    json_files = sorted([
        os.path.join(TEST_DIR, f)
        for f in os.listdir(TEST_DIR)
        if f.lower().endswith(".json")
    ])

    total = 0
    for fp in json_files:
        process_file(fp)
        total += 1

    print(f"\n===== 完成，共扫描 {total} 个文件 =====")


if __name__ == "__main__":
    main()
