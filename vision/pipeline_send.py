from ultralytics import YOLO
from rapidocr import RapidOCR
import cv2
import re
import json
import os

# ==================== 1. 初始化模型与配置 ====================
print("正在加载 YOLO 和 OCR 模型...")
# 把原本的 .pt 改成 .onnx
yolo_model = YOLO('/home/bianbu/deploy/models/vision/best.onnx')#相对路径
ocr_engine = RapidOCR()

# 待测试的图片路径（请确保该图里有你想测的目标，比如电机、水表、灯柱）
img_path = r'/home/bianbu/deploy/test_jpgs/14.jpg'
img = cv2.imread(img_path)

if img is None:
    print(f"❌ 找不到图片，请检查路径: {img_path}")
    exit()

# ==================== 2. YOLO 预测 ====================
# iou=0.5 会把重叠度很高的框合并掉，只留最大的那个
results = yolo_model(img, conf=0.45, iou=0.5) 
all_devices_info = [] # 用来收集图中所有识别到的设备信息

# ==================== 3. 遍历预测框处理逻辑 ====================
for box in results[0].boxes:
    conf = float(box.conf[0])
    cls_id = int(box.cls[0])
    class_name = yolo_model.names[cls_id]
    # 👇 加上这行！打印 YOLO 所有的预测结果
    print(f"🔍 [YOLO原始预测] 类别: {class_name}, 置信度: {float(box.conf[0]):.2f}")
    # 获取坐标并加上外扩边距
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    padding = 5
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img.shape[1], x2 + padding)
    y2 = min(img.shape[0], y2 + padding)
    
    roi = img[y1:y2, x1:x2]
    if roi.size == 0:
        continue

       # -------------------- 场景 A：处理电机/水泵铭牌 --------------------
    if class_name == 'nameplate':
        print(f"\n--- 发现铭牌区域 ({x1}, {y1})，正在识别文字 ---")
        
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        roi_enlarged = cv2.resize(roi_gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        
        output = ocr_engine(roi_enlarged)
        if output.txts:
            for text in output.txts:
                print(f"识别到: {text}")
                
            full_text = " ".join(output.txts)
            
                              # 正则提取（超强空格容忍版 + 类型安全版）
            model_match = re.search(r'([A-Z0-9]+\s+[A-Z0-9]+-[A-Z0-9-]+)', full_text)
            if not model_match:
                model_match = re.search(r'([A-Z0-9]+-[A-Z0-9-]+)', full_text)
            
            power_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:KW|W)', full_text, re.IGNORECASE)
            
            # 电压的智能化提取（直接把结果变成字符串，不再保留 Match 对象）
            voltage_str = None
            v_strict = re.search(r'(380|220/380|400)\s*V', full_text, re.IGNORECASE)
            if v_strict:
                voltage_str = v_strict.group(1)
            else:
                v_loose = re.search(r'\b(380)\b', full_text)
                if v_loose:
                    voltage_str = v_loose.group(1)
                else:
                    v_fallback = re.search(r'(\d{2,3})\s*V', full_text, re.IGNORECASE)
                    if v_fallback:
                        voltage_str = v_fallback.group(1)
            
            speed_match = re.search(r'(\d+)\s*(?:r/min|rpm)', full_text, re.IGNORECASE)
            
            # 组装 JSON（注意：这里统一用刚才提取好的字符串变量，绝不再调 .group()）
                      # 在 for box 循环的最上面获取置信度
            # conf = float(box.conf[0])  <-- 确保你的代码里有这一行
            has_pump = any(yolo_model.names[int(b.cls[0])] == 'pump' for b in results[0].boxes)
            device_type = "pump" if has_pump else "motor"
            motor_info = {
                "设备类型": device_type,
                "型号": model_match.group(1) if model_match else "未识别到型号",
                "功率": (power_match.group(1) + " KW") if power_match else "未识别到功率",
                "电压": (voltage_str + " V") if voltage_str else "未识别到电压",
                "转速": (speed_match.group(1) + " r/min") if speed_match else "未识别到转速",
                "置信度": conf  # 👈 新增置信度
            }
            all_devices_info.append(motor_info)

    # -------------------- 场景 B：处理表计（水表/电表） --------------------
    elif class_name == 'gauge':
        print(f"\n--- 发现表计区域 ({x1}, {y1})，正在识别读数 ---")
        
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        roi_enlarged = cv2.resize(roi_gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        
        output = ocr_engine(roi_enlarged)
        
        meter_model = "未知型号"
        meter_reading = "未识别到读数"
        
        if output.txts:
            for text in output.txts:
                print(f"识别到: {text}")
                
            full_text = " ".join(output.txts)
            print(f"\n【排查信息】OCR 原始拼接文本: {full_text}")
            
                        # 清洗文本
            compact_text = full_text.upper().replace(" ", "").replace("·", "").replace("³", "3")
            compact_text = compact_text.replace('O', '0').replace('Q', '0')
            
            # 👇 核心修改 1：智能判断设备类型
            device_type = "meter"
            if "KWH" in compact_text or "电能表" in compact_text or "电表" in compact_text:
                device_type = "electricity_meter"
            elif "M3" in compact_text or "水表" in compact_text:
                device_type = "water_meter"

                                    # 👇 核心修改 2：型号提取（通用版）
            meter_model = "未知型号"
            # 匹配 DD 或 DDS 开头的电表型号
            model_match_elec = re.search(r'((?:DDS|DD)\d+[A-Z]?(?:-\d+)?)', compact_text)
            # 找水表型号
            model_match_water = re.search(r'([A-Z]{3,}-\d+[A-Z]?)', compact_text)
            
            if model_match_elec:
                meter_model = model_match_elec.group(1) 
            elif model_match_water:
                meter_model = model_match_water.group(1)
            else:
                company_match = re.search(r'([\u4e00-\u9fa5]{2,8}(有限公司|仪表|水表|电表|厂))', full_text)
                if company_match:
                    meter_model = company_match.group(1)

            # 👇 核心修改 3：读数提取（绝对防御版）
            meter_reading = "未识别到读数"
            
            # 策略A：尝试用 KWH 锚点抓（前后都试一次）
            kwh_match = re.search(r'([0-9]{4,6})[- ]?K[- ]?W[- ]?H|K[- ]?W[- ]?H[- ]?([0-9]{4,6})', compact_text)
            if kwh_match:
                # 取非空的那个匹配组
                meter_reading = kwh_match.group(1) if kwh_match.group(1) else kwh_match.group(2)
            else:
                # 策略B：全局暴力扫描。用 (?<!\d) 确保不粘连数字，防止 360 被粘连成 22465360
                nums = re.findall(r'(?<!\d)\d{4,6}(?!\d)', compact_text)
                
                # 恶鬼黑名单（年份、标准号、出厂编号、刻度线等）
                black_list = ['15283', '17215', '2008', '1994', '1200', '360', '10000', '1000', '7666', '00001092', '00000011', '82002992', '2006', '2004', '2005']
                
                for n in nums:
                    if n in black_list:
                        continue
                    if n.startswith('20') and len(n) == 4: # 排除20开头的4位年份
                        continue
                    
                    meter_reading = n
                    break

                # 策略C：如果暴力扫描还是没找到，退回去找水表 H 锚点
                if meter_reading == "未识别到读数":
                    read_match = re.search(r'H\s*([0-9\s]{4,7})', compact_text)
                    if read_match:
                        temp_read = read_match.group(1).replace(" ", "")
                        if len(temp_read) >= 4:
                            meter_reading = temp_read[:4]
            meter_info = {
                "设备类型": device_type,
                "型号": meter_model,
                "当前读数": meter_reading,
                "置信度": conf  # 👈 新增置信度
            }
            all_devices_info.append(meter_info)
    # -------------------- 场景 C：处理指示灯柱 --------------------
    elif class_name == 'light':
        print(f"\n--- 发现灯柱区域 ({x1}, {y1})，正在分析颜色状态 ---")
        
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # 1. 红色 HSV 范围（红色在色相环两端，需要两个范围相加）
        mask_red1 = cv2.inRange(hsv_roi, (0, 100, 100), (10, 255, 255))
        mask_red2 = cv2.inRange(hsv_roi, (160, 100, 100), (180, 255, 255))
        mask_red = mask_red1 + mask_red2
        
        # 2. 绿色 HSV 范围
        mask_green = cv2.inRange(hsv_roi, (40, 100, 100), (80, 255, 255))
        
        # 3. 黄色/橙色 HSV 范围 (新增！)
        mask_yellow = cv2.inRange(hsv_roi, (15, 100, 100), (35, 255, 255))
        
        # 统计像素
        red_pixels = cv2.countNonZero(mask_red)
        green_pixels = cv2.countNonZero(mask_green)
        yellow_pixels = cv2.countNonZero(mask_yellow)
        
        status = "未亮灯/状态未知"
        max_pixels = max(red_pixels, green_pixels, yellow_pixels)
        
        # 判断逻辑（谁的像素最多，就是谁亮着，且要求像素数量大于 50 防止噪点）
        if max_pixels > 50:
            if max_pixels == red_pixels:
                status = "红灯亮起 (故障/报警)"
            elif max_pixels == green_pixels:
                status = "绿灯亮起 (正常运行)"
            elif max_pixels == yellow_pixels:
                status = "黄灯亮起 (警告/待机)"
            
        print(f"颜色分析结果 -> 红: {red_pixels}, 绿: {green_pixels}, 黄: {yellow_pixels} | 状态: {status}")       
        light_info = {
                "设备类型": "tower_light",
                "设备状态": status,
                "置信度": conf  # 👈 新增置信度
            }
        all_devices_info.append(light_info)
    # -------------------- 场景 D：处理普通设备（水泵/电机）本体 --------------------
    elif class_name in ['pump', 'motor']:
        print(f"\n--- 发现设备 ({class_name}) ---")
        device_info = {
            "设备类型": class_name,
            "型号": "未识别到型号",  # 外壳本身没字，不用 OCR
            "当前读数": "N/A",
            "设备状态": "normal",
            "置信度": conf
        }
        all_devices_info.append(device_info)
        
# ==================== 4. 生成基础汇总报告 (result.json) ====================
print("\n" + "="*30)
print("✅ 巡检报告数据汇总")
print("="*30)
if len(all_devices_info) > 0:
    print(json.dumps(all_devices_info, ensure_ascii=False, indent=2))
    with open('result.json', 'w', encoding='utf-8') as f:
        json.dump(all_devices_info, f, ensure_ascii=False, indent=2)
else:
    print("⚠️ 这张图里没有发现可识别的设备。")

# ==================== 5. 生成团队协作接口文件 ====================
print("\n" + "="*30)
print("✅ 开始生成团队协作接口文件")
print("="*30)

# ① 生成 vision_labels.json (标签表)
labels_data = ["motor", "nameplate", "gauge", "tower_light"]
with open('vision_labels.json', 'w', encoding='utf-8') as f:
    json.dump(labels_data, f, ensure_ascii=False, indent=2)
print("1. 已生成 vision_labels.json")

# ② 生成 vision_schema.json (数据结构字典 - 包含 confidence 和嵌套层级)
schema_data = {
    "type": "object",
    "properties": {
        "vision": {
            "type": "object",
            "properties": {
                "device_type": {"type": "string", "description": "设备类型，如 motor, water_meter"},
                "model": {"type": "string", "description": "设备型号或厂家名称"},
                "reading": {"type": "string", "description": "仪表当前读数，没有则为 N/A"},
                "status": {"type": "string", "enum": ["normal", "alarm", "unreadable"], "description": "设备状态"},
                "confidence": {"type": "number", "description": "模型识别置信度，保留两位小数"}
            }
        }
    }
}
with open('vision_schema.json', 'w', encoding='utf-8') as f:
    json.dump(schema_data, f, ensure_ascii=False, indent=2)
print("2. 已生成 vision_schema.json")

# ③ 生成 vision_sample_outputs.jsonl (严格对标大模型接口规范)
with open('vision_sample_outputs.jsonl', 'w', encoding='utf-8') as f:
    if len(all_devices_info) == 0:
        # 没识别到时的兜底
        fallback = {"vision": {"device_type": "none", "model": "未识别", "reading": "N/A", "status": "unreadable", "confidence": 0.0}}
        f.write(json.dumps(fallback, ensure_ascii=False) + "\n")
    else:
        # 设置报警阈值：置信度低于 0.5 的，直接判定为不可读 (unreadable)
        CONFIDENCE_THRESHOLD = 0.5 
        
        for item in all_devices_info:
            dev_type = item.get("设备类型", "unknown")
            model = item.get("型号", "unknown")
            reading = item.get("当前读数", "N/A")
            dev_status = item.get("设备状态", "")
            conf = item.get("置信度", 0.0) # 获取置信度

            # 1. 处理 model 字段 (如果没有型号，用设备类型顶上)
            meter_id = model if model not in ["未知型号", "未识别到型号"] else dev_type
            if dev_type == "tower_light": 
                meter_id = "tower_light"

            # 2. 处理 reading 字段
            final_reading = reading if reading != "未识别到读数" else "N/A"

            # 3. 核心：结合置信度和设备状态，映射 status
            final_status = "normal"
            
            if conf < CONFIDENCE_THRESHOLD:
                final_status = "unreadable"
            else:
                if dev_type == "tower_light":
                    if "红灯" in dev_status or "黄灯" in dev_status:
                        final_status = "alarm"
                    elif "绿灯" in dev_status:
                        final_status = "normal"
                    else:
                        final_status = "unreadable"
                elif dev_type in ["water_meter", "electricity_meter"]:
                    if final_reading == "N/A":
                        final_status = "unreadable"

            # 4. 严格按照 C 同学要求的嵌套格式组装
            standard_output = {
                "vision": {
                    "device_type": dev_type,
                    "model": meter_id,
                    "reading": final_reading,
                    "status": final_status,
                    "confidence": round(conf, 2) # 保留两位小数
                }
            }
            
            # 写入 JSONL
            f.write(json.dumps(standard_output, ensure_ascii=False) + "\n")

print("3. 已生成 vision_sample_outputs.jsonl (严格对标大模型嵌套格式)")
# ④ 生成 threshold_config.json (阈值配置文件 - 加入视觉阈值)
threshold_data = {
    "vision_confidence_threshold": 0.5,   # 新增：视觉 YOLO 置信度阈值
    "ocr_confidence_threshold": 0.5,      # 新增：文字识别置信度阈值
    "audio_volume_threshold": 0.8         # 保留你原来的音频阈值
}
with open('threshold_config.json', 'w', encoding='utf-8') as f:
    json.dump(threshold_data, f, ensure_ascii=False, indent=2)
print("4. 已生成 threshold_config.json")

print("\n🚀 全部生成完毕！请将生成的 4 个 json/jsonl 文件打包发送给 C 同学和 D 同学。")
# ==================== 新增：发送给C模块 ====================
import socket
if all_devices_info:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 9000))
        # 取识别到的第一个设备发送
        dev = all_devices_info[0]
        payload = {
            "vision": {
                "device_type": dev.get("设备类型", "unknown"), 
                "model": dev.get("型号", "unknown"), 
                "reading": dev.get("当前读数", "N/A"), 
                "status": "alarm" if "红灯" in dev.get("设备状态", "") else "normal", 
                "confidence": round(dev.get("置信度", 0.0), 2)
            }
        }
        s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode('utf-8'))
        print(f"✅ B(视觉) 数据已发送给 C 模块: {payload}")
        s.close()
    except Exception as e:
        print(f"❌ B 发送失败: {e}")