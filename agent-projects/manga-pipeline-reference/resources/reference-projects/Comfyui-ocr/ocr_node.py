import torch
import numpy as np
from PIL import Image
import cv2
import json

def convert_numpy_to_python(obj):
    """递归转换numpy对象为Python原生类型，用于JSON序列化"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convert_numpy_to_python(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_to_python(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_to_python(item) for item in obj)
    else:
        return obj

# 检查依赖项
missing_dependencies = []

try:
    from paddleocr import PaddleOCR
    print("PaddleOCR 导入成功")
except ImportError as e:
    print(f"PaddleOCR 导入失败: {e}")
    print("请安装PaddleOCR：pip install paddleocr")
    missing_dependencies.append("paddleocr")
    PaddleOCR = None

try:
    import paddle
    print("PaddlePaddle 导入成功")
except ImportError as e:
    print(f"PaddlePaddle 导入失败: {e}")
    print("请安装PaddlePaddle：pip install paddlepaddle")
    missing_dependencies.append("paddlepaddle")

if missing_dependencies:
    print(f"缺少依赖项: {', '.join(missing_dependencies)}")
    print("请运行以下命令安装：")
    print("pip install paddleocr paddlepaddle opencv-python pillow")

class PaddleOCRNode:
    """
    ComfyUI PaddleOCR 节点
    支持OCR文字识别和坐标标注功能
    """
    
    def __init__(self):
        self.ocr = None
        self.last_config = None  # 记录上次的配置
        
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "language": (["ch", "en", "japanese", "korean"],),
                "use_gpu": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "confidence_threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
            }
        }
    
    RETURN_TYPES = ("STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("recognized_text", "annotated_image", "json_data")
    FUNCTION = "recognize_text"
    CATEGORY = "OCR"
    
    
    def tensor_to_pil(self, tensor):
        """将tensor转换为PIL Image"""
        # 如果tensor是4维的(batch, height, width, channels)，取第一张图
        if len(tensor.shape) == 4:
            tensor = tensor[0]
        
        # 确保tensor在0-1范围内
        if tensor.max() <= 1.0:
            tensor = tensor * 255.0
            
        # 转换为numpy数组
        np_image = tensor.cpu().numpy().astype(np.uint8)
        
        # 转换为PIL Image
        if len(np_image.shape) == 3:
            return Image.fromarray(np_image)
        else:
            return Image.fromarray(np_image, mode='L')
    
    def pil_to_tensor(self, pil_image):
        """将PIL Image转换为tensor"""
        # 转换为RGB模式
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # 转换为numpy数组并归一化
        np_image = np.array(pil_image).astype(np.float32) / 255.0
        
        # 转换为tensor并添加batch维度
        tensor = torch.from_numpy(np_image).unsqueeze(0)
        
        return tensor
    
    def draw_boxes_on_image_official(self, cv_image, ocr_result, transparent_background=True):
        """使用PaddleOCR 3.2.0内置可视化功能"""
        try:
            print(f"🎯 使用PaddleOCR 3.2.0内置可视化功能")
            
            # 检查OCRResult对象是否有内置可视化图像
            if hasattr(ocr_result, 'img') and isinstance(ocr_result.img, dict):
                img_dict = ocr_result.img
                
                if 'ocr_res_img' in img_dict:
                    # 获取内置的可视化图像
                    vis_image = img_dict['ocr_res_img']
                    print(f"✅ 获取到PaddleOCR内置可视化图像: {vis_image.size}")
                    
                    if transparent_background:
                        # 如果需要白色背景，直接返回（内置图像默认是白底）
                        print("🎨 使用内置标注图像（白色背景）")
                        return vis_image
                    else:
                        # 如果需要原图背景，这里可以做进一步处理
                        return vis_image
                else:
                    print("❌ OCRResult没有ocr_res_img，使用备用方法")
                    return self.draw_boxes_on_image_fallback(cv_image, [], transparent_background)
            else:
                print("❌ OCRResult格式不正确，使用备用方法")
                return self.draw_boxes_on_image_fallback(cv_image, [], transparent_background)
            
        except Exception as e:
            print(f"❌ 内置可视化失败: {e}")
            import traceback
            traceback.print_exc()
            return self.draw_boxes_on_image_fallback(cv_image, [], transparent_background)
    
    def draw_boxes_on_image_fallback(self, cv_image, filtered_results, transparent_background=True):
        """备用的简化标注方法"""
        try:
            print("🔄 使用备用绘制方法")
            
            # 转换为PIL图像并直接返回（最简化处理）
            image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            return Image.fromarray(image_rgb)
            
        except Exception as e:
            print(f"❌ 备用绘制方法失败: {e}")
            # 返回白色图像作为最后备用
            return Image.new('RGB', (800, 600), (255, 255, 255))
    
    def recognize_text(self, image, language, use_gpu, confidence_threshold=0.5):
        """执行OCR识别 - 同时输出文本、图像和JSON三种格式"""
        
        # 固定设置这两个参数，用户不可见
        use_textline_orientation = True  # 启用文本行方向分类
        transparent_background = True    # 启用透明背景
        
        print(f"PaddleOCR执行: 语言={language}, 设备={'GPU' if use_gpu else 'CPU'}")
        
        if PaddleOCR is None:
            error_msg = "PaddleOCR未安装，请运行：pip install paddleocr paddlepaddle"
            if missing_dependencies:
                error_msg += f"\n缺少依赖项: {', '.join(missing_dependencies)}"
            return (error_msg, image, json.dumps({"error": "PaddleOCR not installed", "missing_dependencies": missing_dependencies}))
        
        # 初始化PaddleOCR（只在配置变化时重新初始化）
        try:
            current_config = (language, use_gpu, use_textline_orientation)
            if self.ocr is None or self.last_config != current_config:
                # PaddleOCR 3.2.0+ API 更新
                device = 'gpu:0' if use_gpu else 'cpu'
                print(f"{'重新' if self.ocr is not None else ''}初始化 PaddleOCR - 语言: {language}, 设备: {device}, 文本方向: {use_textline_orientation}")
                
                # PP-OCRv5标准配置：按官方文档使用所有必要模块
                print(f"🔧 PP-OCRv5完整5模块配置:")
                print(f"  - 文档图像方向分类: True (必需)")
                print(f"  - 文本图像矫正: True (必需)")
                print(f"  - 文本行方向分类: {use_textline_orientation} (处理竖排文字必需)")
                print(f"  - 文本检测: True (核心功能)")
                print(f"  - 文本识别: True (核心功能)")
                
                # 构建PP-OCRv5完整5模块参数（官方标准配置）
                ocr_params = {
                    'use_textline_orientation': use_textline_orientation,  # 文本行方向分类
                    'use_doc_orientation_classify': True,  # 文档图像方向分类
                    'use_doc_unwarping': True,  # 文本图像矫正
                    'lang': language,
                    'device': device,
                }
                
                self.ocr = PaddleOCR(**ocr_params)
                self.last_config = current_config
                print("PaddleOCR 初始化成功")
        except Exception as e:
            error_msg = f"PaddleOCR 初始化失败: {str(e)}"
            print(error_msg)
            return (error_msg, image, json.dumps({"error": error_msg}))
        
        # 转换tensor为PIL Image
        pil_image = self.tensor_to_pil(image)
        print(f"📐 图像转换信息:")
        print(f"  - 输入tensor shape: {image.shape}")
        print(f"  - PIL图像尺寸: {pil_image.size} (宽x高)")
        print(f"  - PIL图像模式: {pil_image.mode}")
        
        # 转换为numpy数组进行OCR
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        print(f"  - OpenCV图像shape: {cv_image.shape} (高x宽x通道)")
        
        # 执行OCR识别
        try:
            # PaddleOCR 3.2.0返回新的数据格式
            results = self.ocr.ocr(cv_image)
            print(f"🔍 OCR原始结果类型: {type(results)}")
            if results:
                print(f"  - 结果长度: {len(results)}")
                if len(results) > 0:
                    print(f"  - 第一项类型: {type(results[0])}")
            
            # 解析PaddleOCR 3.2.0的新格式
            filtered_results = []
            
            if results and len(results) > 0:
                result = results[0]  # 取第一个结果对象
                
                # 检查是否是OCRResult对象（有rec_texts等属性）
                if hasattr(result, 'rec_texts') and hasattr(result, 'rec_scores'):
                    # PaddleOCR 3.2.0 OCRResult对象
                    rec_texts = getattr(result, 'rec_texts', [])
                    rec_scores = getattr(result, 'rec_scores', [])
                    rec_polys = getattr(result, 'rec_polys', [])
                    dt_polys = getattr(result, 'dt_polys', [])
                    
                    print(f"📊 OCRResult格式解析:")
                    print(f"  - rec_texts数量: {len(rec_texts)}")
                    print(f"  - rec_scores数量: {len(rec_scores)}")
                    print(f"  - rec_polys数量: {len(rec_polys)}")
                    print(f"  - dt_polys数量: {len(dt_polys)}")
                    
                    # 组合结果
                    for i in range(len(rec_texts)):
                        text = rec_texts[i] if i < len(rec_texts) else ""
                        confidence = rec_scores[i] if i < len(rec_scores) else 0.0
                        
                        # 使用检测到的多边形坐标，如果没有则使用识别的多边形
                        poly = rec_polys[i] if i < len(rec_polys) else (dt_polys[i] if i < len(dt_polys) else [])
                        
                        # 调试坐标信息
                        if i < 3:  # 只显示前3个结果的详细信息
                            print(f"  🔍 结果 {i}: 文字='{text}', 置信度={confidence:.3f}")
                            print(f"      原始坐标类型: {type(poly)}")
                            print(f"      原始坐标内容: {poly}")
                        
                        # 转换numpy array为列表
                        if hasattr(poly, 'tolist'):
                            poly = poly.tolist()
                        elif hasattr(poly, '__iter__'):
                            # 处理嵌套的numpy数组
                            try:
                                poly = [[float(x) for x in point] for point in poly]
                            except:
                                poly = []
                        
                        # 调试转换后的坐标
                        if i < 3:
                            print(f"      转换后坐标: {poly}")
                            if len(poly) >= 4:
                                x_coords = [p[0] for p in poly]
                                y_coords = [p[1] for p in poly]
                                print(f"      坐标范围: x({min(x_coords):.1f}-{max(x_coords):.1f}), y({min(y_coords):.1f}-{max(y_coords):.1f})")
                        
                        if confidence >= confidence_threshold and text.strip():
                            filtered_results.append({
                                'text': text,
                                'confidence': confidence,
                                'box': poly
                            })
                            
                elif isinstance(result, dict):
                    # 字典格式
                    rec_texts = result.get('rec_texts', [])
                    rec_scores = result.get('rec_scores', [])
                    rec_polys = result.get('rec_polys', [])
                    
                    for i in range(len(rec_texts)):
                        text = rec_texts[i] if i < len(rec_texts) else ""
                        confidence = rec_scores[i] if i < len(rec_scores) else 0.0
                        poly = rec_polys[i] if i < len(rec_polys) else []
                        
                        if confidence >= confidence_threshold and text.strip():
                            filtered_results.append({
                                'text': text,
                                'confidence': confidence,
                                'box': poly
                            })
                            
                else:
                    # 尝试旧格式处理
                    print("尝试旧格式处理")
                    for i, item in enumerate(results):
                        try:
                            if isinstance(item, (list, tuple)) and len(item) >= 2:
                                box = item[0]
                                text_info = item[1]
                                
                                # 增强的文本信息解析
                                if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                                    text = str(text_info[0])
                                    confidence = float(text_info[1]) if len(text_info) > 1 else 0.0
                                elif isinstance(text_info, str):
                                    text = text_info
                                    confidence = 1.0  # 假设字符串结果置信度为1.0
                                else:
                                    text = str(text_info)
                                    confidence = 0.5  # 默认置信度
                                
                                if confidence >= confidence_threshold:
                                    filtered_results.append({
                                        'text': text,
                                        'confidence': confidence,
                                        'box': box
                                    })
                        except Exception as e:
                            print(f"旧格式处理出错: {e}, item={item}")
                            continue
            
        except Exception as e:
            error_msg = f"OCR识别出错: {str(e)}"
            return (error_msg, image, json.dumps({"error": error_msg}))
        
        # 准备返回数据
        recognized_text = ""
        json_data = {"results": [], "total_count": len(filtered_results)}
        
        # 处理识别结果
        for result in filtered_results:
            try:
                # 新格式：result已经是字典
                if isinstance(result, dict):
                    text = result.get('text', '')
                    confidence = result.get('confidence', 0.0)
                    box = result.get('box', [])
                else:
                    # 旧格式兼容（增强错误处理）
                    box = result[0]
                    text_info = result[1]
                    if isinstance(text_info, (list, tuple)):
                        text = str(text_info[0]) if len(text_info) > 0 else ""
                        confidence = float(text_info[1]) if len(text_info) > 1 else 0.0
                    else:
                        text = str(text_info) if text_info else ""
                        confidence = 0.0
                
                recognized_text += text + "\n"
                
                json_data["results"].append({
                    "text": text,
                    "confidence": confidence,
                    "box": convert_numpy_to_python(box)
                })
            except Exception as e:
                print(f"处理识别结果时出错: {e}, 结果: {result}")
                continue
        
        # 同时生成三种输出格式  
        # 1. 生成标注图像 - 使用PaddleOCR 3.2.0内置可视化
        if filtered_results and results and len(results) > 0:
            # 传入原始OCRResult对象以获取内置可视化
            annotated_pil = self.draw_boxes_on_image_official(
                cv_image, results[0], transparent_background
            )
        else:
            # 如果没有识别结果，返回相应的空图像
            if transparent_background:
                # 创建白色背景的空图像
                annotated_pil = Image.new('RGB', pil_image.size, (255, 255, 255))
                print("📄 无识别结果，创建白色背景图像")
            else:
                # 使用原图
                annotated_pil = pil_image.copy()
                print("📄 无识别结果，使用原图")
        
        annotated_image = self.pil_to_tensor(annotated_pil)
        
        # 2. 文本和JSON会在后续处理
        
        # 准备返回值
        final_text = recognized_text.strip()
        # 转换numpy对象为Python原生类型以便JSON序列化
        clean_json_data = convert_numpy_to_python(json_data)
        final_json = json.dumps(clean_json_data, ensure_ascii=False, indent=2)
        
        print(f"✓ OCR完成: 识别{len(json_data['results'])}个文本块{'，内容: ' + final_text[:30] + ('...' if len(final_text) > 30 else '') if final_text else ''}")
        
        return (final_text, annotated_image, final_json)
    
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # 每次都重新执行
        return float("NaN")
    
    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        # 验证输入参数
        return True

