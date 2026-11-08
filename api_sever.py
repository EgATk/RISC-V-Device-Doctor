from fastapi import FastAPI
 import time
 app = FastAPI(title="竞赛板子控制API")
 # 测试连通性
 @app.get("/ping")
 def ping():
     return {"status": "ok", "time": time.time()}
 # 获取板子状态，后面可以加NPU、外设状态
 @app.get("/board_status")
 def board_status():
     return {
         "npu": "ready",
         "camera": "not_ready",
         "audio": "not_ready"
     }
 # 示例：执行自定义任务接口，电脑调用这个下发指令
 @app.get("/task")
 def run_task(cmd: str = ""):
     """
     调用示例：http://板子IP:8000/task?cmd=test
     """
     if cmd == "test":
         return {"result": "测试任务执行成功"}
     elif cmd == "run_infer":
         # 等摄像头、NPU就绪后，这里换成你的推理代码
         return {"result": "准备执行NPU推理"}
     else:
         return {"result": "未知指令"}
 if __name__ == "__main__":
     import uvicorn
     # host=0.0.0.0 局域网电脑才能访问！非常关键
     uvicorn.run("api_sever:app", host="0.0.0.0", port=8000)
