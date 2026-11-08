# RISC-V-Device-Doctor
基于K1 RISC-V板卡的多模态工业设备巡检系统（音频CNN+YOLO视觉+本地大模型）
```markdown
# RISC-V-Device-Doctor (设备听诊师)

> **面向旋转设备的声-视融合边缘巡检终端**
> 本项目基于进迭时空 K1 (MUSE Pi Pro) RISC-V 开发板，构建了一套完全离线的多模态工业设备故障诊断系统。通过融合**声学 CNN 听诊**、**视觉 YOLO 识别**与**本地大模型决策**，实现从数据采集到维修工单生成的全链路边缘计算闭环。

## 🛠️ 系统架构与目录结构

本仓库采用高度解耦的微服务架构，各模块通过标准 JSON 契约进行数据交互：

```text
RISC-V-Device-Doctor/
├── api_sever.py        # 本地大模型 API 服务端
├── run.py              # [前置启动项] 启动 API 服务及多模态总控
├── audio_module/       # [模块A] 声学诊断（特征提取 + CNN推理 + JSON输出）
│   ├── auto_diagnose.py
│   ├── fault_cnn_5class.onnx
│   └── README.md       # 详见模块内部文档
├── vision/             # [模块B] 视觉识别（YOLOv8 + 目标检测 + 状态分析）
│   ├── pipeline.py
│   ├── best.onnx
│   ├── data.yaml
│   └── README.md       # 详见模块内部文档
└── fusion_module/      # [模块C] 多模态融合与大模型决策（生成维修工单）
    ├── fusion_server.py
    └── README.md       # 详见模块内部文档
```

提示：各模块的核心算法原理、详细依赖及运行说明，请直接查阅对应文件夹内的 README.md。

---

快速开始 (Quick Start)

1. 环境依赖 (RISC-V 专属)

注意：本项目运行于 RISC-V 架构，请勿直接 pip 安装普通的 onnxruntime。

```bash
# 1. 安装系统级依赖与 NPU 加速引擎
sudo apt update
sudo apt install spacemit-onnxruntime python3-spacemit-ort libsndfile1 ffmpeg -y
sudo apt install build-essential cmake git -y

# 2. 安装 Python 业务依赖
pip install numpy opencv-python requests soundfile
# 注：RISC-V 下直接编译 scipy 极慢，推荐使用专属源：
pip install scipy -i https://pypi.riseproject.dev/simple
```

2. 模型准备

· 小模型：声学 CNN (fault_cnn_5class.onnx) 与视觉 YOLO (best.onnx) 已直接包含在仓库中。
· 大模型：由于体积限制，Qwen2.5-0.5B (INT4) 量化模型请从以下网盘链接下载，并放置于根目录：
  · 下载链接：[https://pan.baidu.com/s/1xINCMF1sTg1E6s6IWQ4pmw?pwd=1234]
  · 提取码：1234
  · 也可在板端通过魔搭直接拉取（详见技术文档）。

3. 运行系统

本项目采用 run.py 作为统一入口。需首先启动大模型 API 服务（前置条件），然后执行融合诊断。

```bash
# 启动 API 服务与总控程序
python3 run.py
```

---

运行结果示例

系统完成一次端到端巡检后，将输出结构化的故障诊断 JSON 以及本地大模型生成的维修建议工单（详见技术文档）。


```
