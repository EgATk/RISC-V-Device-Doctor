# B模块：视觉感知与结构化提取 (pipeline.py)

 1. 模块简介
本模块是整个系统的“眼睛”，负责工业现场的视觉感知。基于 **YOLOv8n + RapidOCR** 构建轻量级级联流水线，通过接收图像/视频流，实现对电机、水泵、水表、电表及指示灯柱的精准定位、参数提取与状态识别。最终将非结构化的图像数据转化为标准 JSON，并通过 Socket 发送给融合模块。

 2. 运行环境
- Python 3.8+
- 依赖库：`ultralytics`, `rapidocr`, `opencv-python` (运行 `pip install -r requirements.txt` 安装)
- 模型文件：训练好的 YOLOv8 权重文件（支持 `.pt` 或边缘端部署的 `.onnx` 格式）

 3. 接口协议 (Socket)
本模块作为 TCP Client，将推理结果发送至融合模块指定的 IP 和端口（默认 `9000`）。
- **B模块 (视觉) 发送格式**：
  ```json
  {
    "vision": {
      "device_type": "electricity_meter", 
      "model": "DDS7666", 
      "reading": "000004", 
      "status": "normal", 
      "confidence": 0.88
    }
  }
字段枚举说明：

device_type：motor / water_meter / electricity_meter / tower_light

status：normal (正常) / alarm (红灯警告) / unreadable (模糊或未识别，需人工复核)
4. 技术实现与优化策略
1.级联检测流水线：先用 YOLO 精准定位铭牌/表盘 ROI，再由 OpenCV 进行灰度化与倍率放大，最后交由 RapidOCR 识别，大幅提升小字识别率。
2.抗干扰正则引擎（核心优化）：针对 OCR 排版乱码、空格粘连等问题，引入容错正则（如容忍 220 KW 的空格）与上下文锚点（抓取 kWh 前的纯数字），并结合工业先验知识（电压不可能为 12V）排除端子号干扰。
3.防幻觉黑名单机制：针对年份（如 2018）、国标号（GB/T...）、出厂编号（全0），在后处理层进行严格过滤。宁可输出 unreadable，绝不向大模型投喂脏数据。
4.多模态状态感知：对指示灯柱，利用 OpenCV 转换至 HSV 色彩空间，通过红、绿、黄像素占比统计，实时判断设备运行状态。
5.置信度阈值截断：设定 confidence < 0.5 时，强制将状态置为 unreadable，确保输出数据的绝对可靠性。
5. 部署说明
1.确保已安装相关依赖并准备好训练好的模型文件。
2.运行视觉推理流水线并生成接口文件：
python pipeline.py
(运行后会生成 vision_sample_outputs.jsonl 等规范数据)
3.启动 Socket 客户端发送数据（需确保目标 IP 地址配置正确）：
python send_vision.py
4.提示成功后，融合模块即可实时接收视觉数据
