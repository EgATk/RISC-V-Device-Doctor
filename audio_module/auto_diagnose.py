import numpy as np
import onnxruntime as ort
import json
import cv2
import spacemit_ort
from scipy.io import wavfile
from scipy import signal

audio_path = "/home/bianbu/test_wavs/motor.wav"
model_path = "/home/bianbu/deploy/models/audio/fault_cnn_5class.onnx"
classes = ["bearing_wear", "imbalance", "looseness", "phase_loss", "normal"]
TARGET_HEIGHT = 128
TARGET_WIDTH = 188


def main():
    print("🎧 [1/3] 正在读取音频...")
    sr, y = wavfile.read(audio_path)
    if len(y.shape) > 1:
        y = np.mean(y, axis=1)
    y = y.astype(np.float32)

    print("👁️ [2/3] 正在提取梅尔频谱特征...")
    f, t, Sxx = signal.spectrogram(y, sr, nperseg=512, noverlap=160)
    log_Sxx = 10 * np.log10(Sxx + 1e-9)
    data_resized = cv2.resize(log_Sxx, (TARGET_WIDTH, TARGET_HEIGHT))
    input_data = data_resized.astype(np.float32).reshape(1, 1, TARGET_HEIGHT, TARGET_WIDTH)

    print("🤖 [3/3] CNN 模型正在分析声音...")
    session = ort.InferenceSession(model_path,providers=['SpaceMITExecutionProvider'])#CPU模式下即providers=['CPUExecutionProvider']，NPU模式下即providers=['SpaceMITExecutionProvider']
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_data})
    raw_preds = outputs[0][0]

    exp_preds = np.exp(raw_preds - np.max(raw_preds))
    predictions = exp_preds / np.sum(exp_preds)

    # 👇 核心：提取变量
    predicted_index = np.argmax(predictions)
    fault_type = classes[predicted_index]
    confidence = float(predictions[predicted_index])

    print(f"   -> 听觉诊断结果：【{fault_type}】 (置信度: {confidence * 100:.2f}%)")

    # 👇 生成 JSON
    print("\n📦 正在生成 JSON...")
    result_json = {
        "audio": {
            "fault_class": fault_type,
            "confidence": round(confidence, 2)
        }
    }

    output_file = "/home/bianbu/deploy/logs/audio_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_json, f, ensure_ascii=False, indent=4)

    print(f"✅ 成功！文件已保存至: {output_file}")
    print(json.dumps(result_json, ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()
