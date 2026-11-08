import subprocess
import time
import sys
import os
import json

def kill_port(port):
    """清理残留的端口进程"""
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(1)
    except Exception:
        pass

def main():
    print("🚀 ==========================================")
    print("   工业设备多模态听诊系统 - 一键启动总控程序")
    print("============================================")

    print("\n🧹 正在清理残留的 9000 端口...")
    kill_port(9000)

    # 1. 启动 C 模块 (融合服务) -> 使用 vision_env
    print("\n[1/3] 正在后台启动 C 模块 (融合大脑)...")
    c_process = subprocess.Popen(
        [sys.executable, "-u", "fusion_server.py"],
        cwd="c_module",  
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    time.sleep(2) 
    print("✅ C 模块已启动！")

    # 2. 运行 A 模块 (听觉) -> 切换使用 k1_env
    print("\n[2/3] 正在执行 A 模块 (听觉诊断)...")
    k1_python = os.path.expanduser("~/k1_env/bin/python")
    if not os.path.exists(k1_python):
        print(f"⚠️ 警告: 找不到 {k1_python}，尝试用默认环境运行...")
        k1_python = sys.executable
        
    subprocess.run([k1_python, "scripts/auto_diagnose_send.py"])
    
    #yanshi
    time.sleep(3)
    
    # 3. 运行 B 模块 (视觉) -> 使用 vision_env
    print("\n[3/3] 正在执行 B 模块 (视觉识别)...")
    subprocess.run([sys.executable, "scripts/pipeline_send.py"])

    print("\n⏳ 数据已发送！等待 C 模块进行融合推理 (约 15 秒超时降级)...")
    
    # 4. 轮询读取 C 模块的输出
    start_time = time.time()
    final_result = ""
    while time.time() - start_time < 25: 
        line = c_process.stdout.readline()
        if line:
            line = line.strip()
            print(f"[C模块] {line}")
            if "[已返回]" in line:
                final_result = line.replace("[已返回]", "").strip()
                break 
    
    print("\n================ 最终巡检验收单 ================")
    if final_result:
        try:
            parsed_json = json.loads(final_result)
            print("🔔 报警等级:", parsed_json.get("level"))
            print("📝 诊断结论:", parsed_json.get("conclusion"))
            print("📄 自动工单:", parsed_json.get("ticket"))
        except:
            print(final_result)
    else:
        print("⚠️ 没有收到 C 模块的返回结果，请检查上方 C 模块的日志报错。")
    print("================================================")

    print("\n🛑 正在关闭 C 模块...")
    c_process.terminate()
    print("=========== 系统运行结束 ===========")

if __name__ == "__main__":
    main()
