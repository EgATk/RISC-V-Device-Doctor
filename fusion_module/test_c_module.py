import socket
import json
import time

def test_fusion():
    print("尝试连接 C 模块...")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(('127.0.0.1', 9000))
        print("✅ 连接成功，开始发送模拟数据")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 模拟数据
    audio_data = {"audio": {"fault_class": "bearing_wear", "confidence": 0.92}}
    vision_data = {"vision": {"device_type": "pump", "model": "pump", "reading": "N/A", "status": "alarm", "confidence": 0.98}}

    # ⏱️ 记录开始发送的时间
    start_time = time.perf_counter()

    client.sendall((json.dumps(audio_data) + "\n").encode('utf-8'))
    time.sleep(1)
    client.sendall((json.dumps(vision_data) + "\n").encode('utf-8'))
    print("📤 数据发送完毕，等待 C 模块返回结果...")

    try:
        # 接收结果
        response = client.recv(4096).decode('utf-8')
        
        # ⏱️ 记录收到结果的时间
        end_time = time.perf_counter()
        
        print(f"\n🎉 [收到最终工单]: \n{response}")
        print(f"=====================================")
        print(f"⏱️ C 模块实际处理耗时: {(end_time - start_time)*1000:.2f} 毫秒")
        print(f"=====================================")
        
    except Exception as e:
        print(f"接收数据失败: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    test_fusion()