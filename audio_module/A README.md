端到端推理：一条命令实现“音频读取 -> 特征提取 -> 模型推理 -> 结果输出”。

边缘NPU加速：将轻量级 CNN 模型转化为 .onnx 格式，结合 spacemit-onnxruntime 实现本地硬件加速。

多模态解耦：输出标准 JSON 数据，无缝对接视觉模块与大模型融合模块。

快速开始 (Quick Start)

1. 环境依赖
 注意：本模块运行于 RISC-V 平台，必须使用进迭时空官方适配版推理引擎，请勿直接 pip 安装普通的 onnxruntime。

```bash
pip install numpy scipy opencv-python requests
sudo apt update
sudo apt install spacemit-onnxruntime python3-spacemit-ort -y
```

2. 运行推理

将需要测试的音频文件命名为 motor.wav 放在当前目录下（或在代码中修改路径），直接执行：

```bash
python3 auto_diagnose.py
```
文件结构

auto_diagnose.py：核心推理脚本。
fault_cnn_5class.onnx / .data：训练好的 5 分类 CNN 模型。
audio_output.json：生成的标准化输出样例。
输出规范

运行成功后，终端会打印诊断结果，并生成供大模型融合模块调用的 audio_output.json：

```json
{
    "audio": {
        "fault_class": "bearing_wear",
        "confidence": 0.95
    }
}
```

支持分类：normal(正常), bearing_wear(轴承磨损), imbalance(不平衡), looseness(松动), phase_loss(缺相)。

性能指标

测试准确率：100% (基于当前测试集)
模型体积：极轻量（< 1MB），适合边缘部署。
推理延迟：毫秒级响应，远低于系统 1s 延迟要求。
