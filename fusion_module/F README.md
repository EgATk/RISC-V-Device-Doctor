[README.md](https://github.com/user-attachments/files/34425757/README.md)
# C模块：多模态融合与交互业务 (fusion_server.py)

## 1. 模块简介
本模块是整个系统的“大脑”，负责接收 A（音频）和 B（视觉）推理出的 JSON 结果，通过规则引擎进行多模态对齐融合，并调用本地部署的轻量化大语言模型（Qwen-0.5B），生成人类可读的巡检结论和自动化工单。

## 2. 运行环境
- Python 3.8+
- 依赖库：`requests` (运行 `pip install requests` 安装)
- 大模型服务：本地运行 Ollama (需拉取 `qwen2:0.5b` 或 `qwen2.5:0.5b`)

## 3. 接口协议 (Socket)
本模块作为 TCP Server，监听 `9000` 端口。
- **A模块 (音频) 发送格式**：
  `{"audio": {"fault_class": "bearing_wear", "confidence": 0.95}}`
- **B模块 (视觉) 发送格式**：
  `{"vision": {"device_type": "motor", "model": "YE2 355M-4", "status": "alarm", "confidence": 0.88}}`
- **返回格式**：
  `{"level": "高置信报警", "conclusion": "巡检结论...", "ticket": "【自动工单】..."}`

## 4. 技术实现与优化策略 
- **多模态规则对齐**：采用时间窗口缓存机制，等待 A 和 B 数据齐备后统一处理，避免单模态误判。
- **高可靠降级设计（核心优化）**：如果本地大模型推理超时（设为10秒）或崩溃，系统会自动触发 Fallback 机制，直接返回基于模板的结构化结论，确保工业现场系统永不死机、永不阻塞。
- **Prompt 工程约束**：在提示词中严格限制 LLM 的生成范围，禁止其编造未检测到的故障，仅负责语义润色。

## 5. 部署说明
1. 确保 Ollama 在后台运行（`ollama serve`）。
2. 运行服务：`python fusion_server.py`。
3. 启动成功后会打印：`[启动] 融合服务已启动，监听 0.0.0.0:9000`。
