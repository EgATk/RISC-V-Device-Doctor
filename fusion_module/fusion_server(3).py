import socket
import json
import threading
import requests
import os

# ================= 配置信息 =================
TCP_IP = '0.0.0.0'   # 监听所有网卡
TCP_PORT = 9000      # C 模块对外服务端口
BUFFER_SIZE = 1024

# llama-server 的默认地址
LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"

# 全局缓存池，用于暂存 A 和 B 发来的数据
data_cache = {}

# ================= 0. RAG 知识库加载 =================
MANUAL_DB = {}
# 【核心修复】获取当前脚本所在的绝对路径，保证永远能找到同目录下的 json
current_dir = os.path.dirname(os.path.abspath(__file__))
manual_path = os.path.join(current_dir, "manual.json")

if os.path.exists(manual_path):
    try:
        with open(manual_path, "r", encoding="utf-8") as f:
            MANUAL_DB = json.load(f)
        print(f"[初始化] 成功加载本地维修手册知识库: {manual_path}")
    except Exception as e:
        print(f"[警告] 加载知识库失败: {e}")
else:
    print(f"[提示] 未找到 manual.json，预期路径为: {manual_path}，将使用默认处理建议。")

# ================= 1. 规则融合决策表 =================
def fuse_logic(audio_data, vision_data):
    audio_cls = audio_data.get("fault_class", "normal")
    audio_conf = audio_data.get("confidence", 0.0)
    
    device_type = vision_data.get("device_type", "unknown")
    meter_model = vision_data.get("model", "未知型号")
    reading = vision_data.get("reading", "N/A")
    vision_status = vision_data.get("status", "normal")
    vision_conf = vision_data.get("confidence", 0.0)

    # 1. 一切正常
    if audio_cls == "normal" and vision_status == "normal":
        return {
            "verdict": "设备运行正常",
            "level": "正常",
            "evidence": {
                "audio": "声音正常", 
                "vision": f"{device_type} 型号{meter_model} 运行正常"
            }
        }
    
    # 2. 音频报警
    if audio_cls == "bearing_wear" and audio_conf > 0.8:
        verdict = "检测到轴承磨损"
        level = "高置信报警"
    elif audio_cls == "looseness" and audio_conf > 0.7:
        verdict = "检测到机械松动"
        level = "报警"
    elif audio_cls == "imbalance" and audio_conf > 0.7:
        verdict = "检测到转子不平衡"
        level = "报警"
    elif audio_cls == "phase_loss" and audio_conf > 0.7:
        verdict = "检测到缺相故障"
        level = "高置信报警"
    # 3. 视觉报警
    elif vision_status == "alarm" and vision_conf > 0.5:
        verdict = f"视觉检测到 {device_type} 异常"
        level = "报警"
    elif vision_status == "unreadable":
        verdict = "视觉识别受阻，建议人工复核"
        level = "预警"
    # 4. 其他疑似
    else:
        verdict = f"系统预警：疑似{audio_cls} (音频) / {vision_status} (视觉)"
        level = "预警"

    return {
        "verdict": verdict,
        "level": level,
        "evidence": {
            "audio": f"{audio_cls} (置信度 {audio_conf})",
            "vision": f"{device_type} (型号: {meter_model}) 读数: {reading}, 状态: {vision_status}"
        }
    }

# ================= 2. 调用大模型生成人话 (带 RAG 增强 + 字数限制) =================
def generate_nlg(fusion_result):
    if fusion_result['level'] == "正常":
        return "设备各项指标正常，未检测到异常。"

    # RAG 检索
    search_key = "meter_alarm" 
    if "轴承" in fusion_result['verdict']:
        search_key = "bearing_wear"
    elif "松动" in fusion_result['verdict']:
        search_key = "looseness"
    elif "缺相" in fusion_result['verdict']:
        search_key = "phase_loss"
    elif "不平衡" in fusion_result['verdict']:
        search_key = "imbalance"
    elif "受阻" in fusion_result['verdict']:
        search_key = "unreadable"

    knowledge = MANUAL_DB.get(search_key, "请按常规工业巡检流程处理，建议现场核查。")
    print(f"[RAG] 命中知识库条目 ({search_key})...")

    # 强指令限制 + 要求极简
    prompt_text = f"""你是一个工业设备巡检助手。请结合【诊断结果】和【维修手册】，用一句简短的中文给出结论和处置建议。
【限制】严禁废话，总字数必须严格控制在 50 到 70 个字之间。

【诊断结果】：
综合判定：{fusion_result['verdict']}
证据：{json.dumps(fusion_result['evidence'], ensure_ascii=False)}

【维修手册参考】：
{knowledge}

请直接输出结论，不要解释，不要编造。"""

    payload = {
        "messages": [
            {"role": "system", "content": "你是一个专业的工业巡检大模型助手，极度精简，只说核心结论和处置建议。"},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.1,  # 降低温度，减少发散
        "max_tokens": 120,   # 限制最大 token 数，加速推理
        "stream": False
    }

    try:
        print("[LLM] 正在请求 llama-server 生成工单...")
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=15)
        response.raise_for_status()
        result_json = response.json()
        reply = result_json["choices"][0]["message"]["content"].strip()
        
        # 代码层硬性截断，防止大模型不听话
        if len(reply) > 80:
            reply = reply[:80] + "..."
            
        return reply

    except Exception as e:
        print(f"\n[警告] LLM 调用失败，启用降级模板: {e}")
        return f"{fusion_result['verdict']}。手册参考：{knowledge}"

# ================= 3. 处理客户端连接 =================
def handle_client(conn, addr):
    print(f"\n[新连接] 来自 {addr}")
    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break
            try:
                msg = json.loads(data.decode('utf-8'))
                print(f"[收到数据] {msg}")
                
                if "audio" in msg:
                    data_cache["audio"] = msg["audio"]
                if "vision" in msg:
                    data_cache["vision"] = msg["vision"]
                
                if "audio" in data_cache and "vision" in data_cache:
                    print("[融合] 音频与视觉数据已齐备，开始融合...")
                    
                    audio_data = data_cache.pop("audio")
                    vision_data = data_cache.pop("vision")
                    
                    # 1. 规则融合
                    fusion_res = fuse_logic(audio_data, vision_data)
                    # 2. RAG + 大模型生成
                    nlg_text = generate_nlg(fusion_res)
                    
                    final_output = {
                        "level": fusion_res["level"],
                        "conclusion": nlg_text,
                        "ticket": f"【自动工单】{nlg_text}"
                    }
                    
                    conn.sendall((json.dumps(final_output, ensure_ascii=False) + "\n").encode('utf-8'))
                    print(f"[已返回] {final_output}\n")
                else:
                    print("[等待] 数据未齐备，继续等待另一路...")
                    
            except json.JSONDecodeError:
                print("[错误] 收到非 JSON 数据")
    except ConnectionResetError:
        pass
    finally:
        conn.close()
        print(f"[断开连接] {addr}")

# ================= 4. 启动服务 =================
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((TCP_IP, TCP_PORT))
    server.listen(5)
    print(f"====================================")
    print(f"[启动] 融合服务已启动，监听 {TCP_IP}:{TCP_PORT}")
    print(f"[提示] 正在连接 llama-server: {LLAMA_SERVER_URL}")
    print(f"====================================")

    while True:
        conn, addr = server.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.start()

if __name__ == "__main__":
    start_server()