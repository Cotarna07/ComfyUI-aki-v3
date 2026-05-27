import json
import json

# Load current workflow
with open('d:\\ComfyUI-aki-v3\\current_workflow.json', 'r', encoding='utf-8') as f:
    wf = json.load(f)

# Modify KSamplerAdvanced nodes
for n in wf['nodes']:
    if n['type'] == 'KSamplerAdvanced':
        nid = n['id']
        title = n.get('title', '')
        print(f"\n=== Original Node {nid} ({title}) ===")
        print(f"  widgets_values: {n['widgets_values']}")
        
        w = n['widgets_values']
        # w[0]=add_noise, w[1]=noise_seed, w[2]=seed_mode, w[3]=steps, w[4]=cfg, 
        # w[5]=sampler_name, w[6]=scheduler, w[7]=start_at_step, w[8]=end_at_step, 
        # w[9]=return_with_leftover_noise
        
        if nid == 86:
            # High Noise Sampling Pass (first pass)
            w[3] = 30                # steps: 5 -> 30
            w[4] = 3.5               # cfg: 1.4 -> 3.5
            w[6] = "sgm_uniform"     # scheduler: simple -> sgm_uniform
            w[7] = 0                 # start_at_step: 0 -> 0 (keep)
            w[8] = 15                # end_at_step: 3 -> 15
            wins = [3, 4, 6, 7, 8]
            labels = ['steps', 'cfg', 'scheduler', 'start_at_step', 'end_at_step']
            
        elif nid == 85:
            # Low Noise Sampling Pass (second pass / refinement)
            w[3] = 30                # steps: 5 -> 30
            w[4] = 3.0               # cfg: 1.1 -> 3.0
            w[6] = "sgm_uniform"     # scheduler: simple -> sgm_uniform
            w[7] = 12                # start_at_step: 2 -> 12
            w[8] = 25                # end_at_step: 7 -> 25
            wins = [3, 4, 6, 7, 8]
            labels = ['steps', 'cfg', 'scheduler', 'start_at_step', 'end_at_step']
        
        print(f"  === Optimized Node {nid} ===")
        for i, lbl in zip(wins, labels):
            print(f"  {lbl}: {w[i]}")

# Save optimized workflow
out_path = 'd:\\ComfyUI-aki-v3\\wan22_optimized_workflow.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"✅ Optimized workflow saved to: {out_path}")
print(f"{'='*60}")
print()
print("Summary of changes:")
print("  KSampler[86] (High Noise Sampling Pass):")
print("    steps: 5 -> 30")
print("    cfg: 1.4 -> 3.5")
print("    scheduler: simple -> sgm_uniform")
print("    start_at_step: 0 -> 0 (unchanged)")
print("    end_at_step: 3 -> 15")
print()
print("  KSampler[85] (Low Noise Sampling Pass):")
print("    steps: 5 -> 30")
print("    cfg: 1.1 -> 3.0")
print("    scheduler: simple -> sgm_uniform")
print("    start_at_step: 2 -> 12")
print("    end_at_step: 7 -> 25")
