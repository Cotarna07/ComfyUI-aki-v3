# 商品视觉导演测试记录：1005007109462323

- 生成时间：`2026-05-27 14:25:12`
- 视觉分析模型：`huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M`（本地 Ollama）
- 使用边界：VLM 用于读取证据、规划镜头和提出风险，不能单独批准真实商品图发布。
- 原始证据图：`01.jpg`, `02.jpg`, `03.jpg`, `04.jpg`, `05.jpg`, `06.jpg`
- 风格参照图：`ChatGPT Image 2026年5月27日 11_32_38 (1).png`, `ChatGPT Image 2026年5月27日 11_32_39 (2).png`, `ChatGPT Image 2026年5月27日 11_32_40 (3).png`, `ChatGPT Image 2026年5月27日 11_32_40 (4).png`（仅作广告视觉参考）

## 逐图证据

### 01.jpg

- 角色/附件状态：Police minifigure standing beside the car
- 拆解或可拆结构：未见明确拆解状态
- 用途：Catalog verification; Product identification; Age/piece count reference

### 02.jpg

- 角色/附件状态：警察小人坐在驾驶座内
- 拆解或可拆结构：车顶模块; 警灯模块
- 用途：确认产品编号; 确认产品类别; 确认产品颜色和标识; 确认产品组装状态; 确认产品包含的配件

### 03.jpg

- 角色/附件状态：警察小人偶站立在警车右侧
- 拆解或可拆结构：未见明确拆解状态
- 用途：

### 04.jpg

- 角色/附件状态：警察小人站立于车旁，手持手电筒
- 拆解或可拆结构：未见明确拆解状态
- 用途：确认产品编号; 确认产品类别; 确认包含角色; 确认车辆配置

### 05.jpg

- 角色/附件状态：警察小人偶坐在驾驶座内
- 拆解或可拆结构：未见明确拆解状态
- 用途：验证产品编号; 确认年龄建议; 确认包装尺寸; 确认产品系列

### 06.jpg

- 角色/附件状态：Minifigure standing beside vehicle; Minifigure holding a megaphone
- 拆解或可拆结构：Lightbar module shown detached above vehicle
- 用途：Catalog verification; Packaging reference for product identity

## 网页端风格拆解

- 高饱和度的蓝色调营造出强烈的警车氛围
- 多角度展示产品细节，增强视觉吸引力
- 背景城市夜景与产品形成对比，突出主体

## 镜头方案

### rain_city_assembled_outside (`creative_campaign`)

- 源图依据：01.jpg, 03.jpg
- 构图：警车置于雨夜城市街道，背景为模糊光斑与动态光轨，警车居中，人偶站立车旁
- 文案方式：大号标题'乐高城市警车' + 小字'Item 60312 | 5+'，置于画面底部

### rain_city_feature_exploded_inside (`creative_campaign`)

- 源图依据：02.jpg, 06.jpg
- 构图：警车正面视角，人偶坐驾驶座，车顶警灯模块悬浮于车顶上方
- 文案方式：大号标题'乐高城市警车' + 小字'Item 60312 | 5+'，置于画面底部

### catalog_factual_clean (`factual_product`)

- 源图依据：03.jpg
- 构图：警车正面，人偶站立车右侧，背景为纯白或浅灰支持面，无城市背景
- 文案方式：大号标题'乐高城市警车' + 小字'Item 60312 | 5+ | 94件'，置于画面底部

### specification_layout_post (`factual_product`)

- 源图依据：05.jpg
- 构图：警车正面，人偶坐驾驶座，背景为纯白或浅灰支持面
- 文案方式：大号标题'乐高城市警车' + 小字'Item 60312 | 5+ | 94件 | 14.1cm x 15.7cm x 4.5cm'，置于画面底部

## 程序门禁

- 镜头方案结构校验：通过
- 规划尝试次数：`1`
- 人工核验警告：VLM 对件数读取得到冲突值：94 (01.jpg); 999 (06.jpg)；排版前必须人工核对原图。

## 重要边界

- 能从原图证据证明的人物位置或拆解状态，可进入对应保真候选分支。
- 未由同一源图证明的配置组合，只能作为创意广告候选，不能冒充真实展示图。
- 标题、件数、年龄与货号应后期排版并回查包装证据，不由生成模型自由书写。
