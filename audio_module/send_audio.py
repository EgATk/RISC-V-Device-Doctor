import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import socket
import json

# 和训练保持一模一样的网络
class FaultCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1,16,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16,32,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Linear(48128, 128), nn.ReLU(),
            nn.Linear(128, 5)
        )
    def forward(self, x):
        x = self.features(x)
        x = torch.flatten(x,1)
        x = self.classifier(x)
        return x

# 类别顺序
classes = ["bearing_wear", "imbalance", "looseness", "phase_loss", "normal"]

# 加载模型
model = FaultCNN()
model.load_state_dict(torch.load("/home/bianbu/deploy/models/audio/fault_cnn_5class_fixed.pth", map_location="cpu"))
model.eval()

# ========== 这里换成你的特征，演示先用 X_test 取一条样本 ==========
X_test = np.load("X_test.npy")
feat_np = X_test[0:1]
feat_tensor = torch.from_numpy(feat_np).float().permute(0,3,1,2)

with torch.no_grad():
    logits = model(feat_tensor)
    prob = F.softmax(logits, dim=1)
    pred_idx = torch.argmax(prob, dim=1).item()
    confidence = prob[0][pred_idx].item()
    fault_name = classes[pred_idx]

# ✅ 构造她要的标准JSON
data = {
    "audio": {
        "fault_class": fault_name,
        "confidence": confidence
    }
}

# ========== Socket 发送部分（重点！） ==========
s = socket.socket()
# ⚠️ 如果是跨设备通信，把 127.0.0.1 改成她电脑真实IP
s.connect(("127.0.0.1", 9000))
# json编码成字节流发送
send_bytes = json.dumps(data).encode()
s.send(send_bytes)
s.close()

print("✅ 发送成功！")
print(json.dumps(data, indent=2))
