from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # THÊM DÒNG NÀY
import requests
from collections import Counter

app = FastAPI()

# ========== THÊM CORS VÀO ĐÂY ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Cho phép tất cả domain
    allow_credentials=True,
    allow_methods=["*"],           # Cho phép tất cả method (GET, POST,...)
    allow_headers=["*"],           # Cho phép tất cả headers
)
# =======================================

SOURCE_API = "http://160.250.5.186:6001/sexy/all"

STATE = {}

# =========================
# THUẬT TOÁN
# =========================
def bcr_predict(history, table_id):
    results = ["PLAYER" if c == "P" else "BANKER" for c in history]

    score = {"BANKER": 0, "PLAYER": 0}

    if len(results) < 2:
        return "SKIP", "0%", "BO"

    # ===== STREAK =====
    last = results[-1]
    streak = 1
    for i in range(len(results)-2, -1, -1):
        if results[i] == last:
            streak += 1
        else:
            break

    if streak >= 3:
        score[last] += 4

    # ===== TỈ LỆ =====
    count = Counter(results)
    if count["BANKER"] > count["PLAYER"]:
        score["BANKER"] += 2
    else:
        score["PLAYER"] += 2

    # ===== NHỊP 1-1 =====
    if results[-1] != results[-2]:
        score[results[-1]] += 2

    # ===== BACKTRACK =====
    if len(results) >= 6:
        pattern = results[-4:]
        for i in range(len(results)-5):
            if results[i:i+4] == pattern:
                score[results[i+4]] += 3
                break

    # ===== CẦU LOẠN =====
    if len(results) >= 6:
        last6 = results[-6:]
        if last6.count("PLAYER") == 3 and last6.count("BANKER") == 3:
            return "SKIP", "0%", "BO"

    # ===== DỰ ĐOÁN =====
    prediction = max(score, key=score.get)

    # ===== STATE ĐẢO =====
    state = STATE.get(table_id, {"wrong": 0, "last_pred": None})
    real_last = results[-1]

    if state["last_pred"]:
        if state["last_pred"] != real_last:
            state["wrong"] += 1
        else:
            state["wrong"] = 0

    if state["wrong"] >= 2:
        prediction = "PLAYER" if prediction == "BANKER" else "BANKER"

    state["last_pred"] = prediction
    STATE[table_id] = state

    # ===== CONFIDENCE =====
    total = score["BANKER"] + score["PLAYER"]
    confidence = round(score[prediction] / total * 100, 2) if total else 50

    # ===== KHUYẾN NGHỊ =====
    if confidence >= 70:
        action = "DANH"
    elif confidence >= 60:
        action = "THAM_KHAO"
    else:
        action = "BO"

    return prediction, f"{confidence}%", action


# =========================
# API
# =========================
@app.get("/predict")
def predict():
    try:
        res = requests.get(SOURCE_API, timeout=5)
        raw = res.json()

        # fix mọi kiểu API
        if isinstance(raw, dict):
            data = raw.get("data") or raw.get("result") or []
        else:
            data = raw

        result = []

        for table in data:
            table_id = table.get("ban")
            history = table.get("ket_qua", "")

            # bỏ qua nếu không có dữ liệu
            if not history or len(history) < 2:
                continue

            du_doan, ti_le, khuyen_nghi = bcr_predict(history, table_id)

            result.append({
                "ban": table_id,
                "so_van": len(history),
                "du_doan": du_doan,
                "ti_le": ti_le,
                "khuyen_nghi": khuyen_nghi,
                "cau": history[-20:]
            })

        # sort theo tỉ lệ cao → thấp
        result = sorted(result, key=lambda x: float(x["ti_le"].replace("%","")), reverse=True)

        return {
            "status": "success",
            "so_ban": len(result),
            "data": result
        }

    except Exception as e:
        return {"error": str(e)}


# =========================
# RUN LOCAL
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
