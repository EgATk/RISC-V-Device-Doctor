import socket
import json
import time
import os

# 目标服务器的 IP 和端口 (已修改为你要求的 IP)
SERVER_IP = "192.168.137.253"
SERVER_PORT = 9000

def send_to_fusion(vision_data):
    """
    通过 Socket 将视觉数据发送到融合模块
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 设置连接超时时间，防止一直卡死
    s.settimeout(5.0) 
    
    try:
        print(f"正在连接 {SERVER_IP}:{SERVER_PORT} ...")
        s.connect((SERVER_IP, SERVER_PORT)) 
        
        # 组装数据，外层必须是 "vision" (C同学要求的规范)
        data = {"vision": vision_data} 
        
        # 序列化为 JSON 字符串，并加上换行符 \n，防止 TCP 粘包
        json_str = json.dumps(data, ensure_ascii=False) + "\n"
        
        # 发送数据
        s.sendall(json_str.encode('utf-8'))
        print("✅ B 发送视觉数据成功:", json_str.strip())
        
    except ConnectionRefusedError:
        print(f"❌ 连接失败：目标主机 {SERVER_IP}:{SERVER_PORT} 拒绝连接。请确认 C/D 同学的接收服务是否已启动。")
    except socket.timeout:
        print(f"❌ 连接超时：请检查网络是否能 ping 通 {SERVER_IP}。")
    except Exception as e:
        print("❌ 发送失败:", e)
    finally:
        s.close()

# ==========================================
# 测试与使用区 (根据你的需求选一种执行)
# ==========================================
if __name__ == "__main__":
    
    # 【方式一】使用你提供的模拟数据进行单条测试
    print("--- 开始单条发送测试 ---")
    result = {
        "device_type": "motor", 
        "model": "YE2 355M-4", 
        "reading": "N/A", 
        "status": "alarm", 
        "confidence": 0.88
    }
    send_to_fusion(result)
    
    time.sleep(1) # 暂停 1 秒
    
    # 【方式二】自动读取你 pipeline 生成的 vision_sample_outputs.jsonl 并逐行发送
    # 如果你想测试真实推理出来的数据，把下面的注释打开
    """
    print("\n--- 开始读取本地 jsonl 文件发送 ---")
    file_path = "vision_sample_outputs.jsonl"
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            if not line.strip(): continue
            # 读取出来的是 {"vision": {...}}，我们需要提取里面的字典
            raw_data = json.loads(line)
            vision_payload = raw_data.get("vision", {})
            
            # 发送
            send_to_fusion(vision_payload)
            time.sleep(0.5) # 稍微停顿一下，防止发太快
    else:
        print(f"找不到文件: {file_path}，请先运行 pipeline.py 生成数据。")
    """
