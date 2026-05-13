from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import base64
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

app.secret_key = "super-secret-key"

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


SYSTEM_PROMPT = """
Ты — AI-консультант по здоровому питанию.
Отвечай понятно, безопасно и структурировано.
Не ставь диагнозы и не назначай лечение.
Если вопрос медицинский — советуй обратиться к врачу.

Ты отвечаешь ТОЛЬКО на темы:
- здоровое питание
- еда и продукты
- калории
- КБЖУ
- похудение
- набор массы
- рацион
- диеты
- спорт и тренировки
- образ жизни
- анализ еды по фото

Если вопрос не связан с этими темами, отвечай только так:
"Я консультирую только по вопросам здорового питания, похудения, КБЖУ, спорта и здорового образа жизни 😊"
"""


ANALYZE_PROMPT = """
Ты анализируешь ИМЕННО изображение еды.

Важно:
- Не придумывай блюдо.
- Если на фото не еда, так и напиши.
- Если блюдо определить сложно, напиши "не удалось точно определить".
- Не отвечай шаблонно.
- Оцени КБЖУ примерно, потому что вес неизвестен.

Формат ответа:

Блюдо: <что изображено на фото>

Калории: <примерно>
Белки: <примерно>
Жиры: <примерно>
Углеводы: <примерно>

Оценка пользы:
<кратко>

Рекомендации:
<практичные советы>
"""


def file_path(filename):
    return os.path.join(os.path.dirname(__file__), filename)


@app.route("/")
def index():
    return send_file(file_path("index.html"))


@app.route("/index.html")
def index_page():
    return send_file(file_path("index.html"))


@app.route("/home.html")
def home_page():
    return send_file(file_path("home.html"))


@app.route("/chat.html")
def chat_page():
    return send_file(file_path("chat.html"))


@app.route("/profile.html")
def profile_page():
    return send_file(file_path("profile.html"))


@app.route("/analyze_food.html")
def analyze_food_page():
    return send_file(file_path("analyze_food.html"))


@app.route("/<path:filename>")
def static_files(filename):
    return send_file(file_path(filename))


@app.route("/analyze", methods=["POST"])
@app.route("/analyze_food", methods=["POST"])
def analyze_food():
    if "image" not in request.files:
        return jsonify({"result": "❌ Файл не найден"})

    image_file = request.files["image"]

    if image_file.filename == "":
        return jsonify({"result": "❌ Фото не выбрано"})

    image_bytes = image_file.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = image_file.mimetype or "image/jpeg"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYZE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_completion_tokens=1000
        )

        analysis_text = response.choices[0].message.content.strip()

        session["last_analysis"] = analysis_text
        session["chat_history"] = []

        return jsonify({"result": analysis_text})

    except Exception as e:
        return jsonify({"result": f"❌ Ошибка анализа: {str(e)}"})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data:
        return jsonify({"answer": "❌ Данные не получены"})

    question = data.get("question", "").strip()

    if not question:
        return jsonify({"answer": "Введите вопрос."})

    allowed_topics = [
        "еда",
        "питание",
        "пища",
        "продукт",
        "продукты",
        "блюдо",
        "здоровье",
        "здоровый образ жизни",
        "зож",
        "похудение",
        "похудеть",
        "сбросить вес",
        "лишний вес",
        "диета",
        "калории",
        "калорийность",
        "ккал",
        "кбжу",
        "белки",
        "белок",
        "жиры",
        "углеводы",
        "рацион",
        "спорт",
        "тренировка",
        "тренировки",
        "фитнес",
        "набор массы",
        "масса",
        "вес",
        "витамины",
        "вода",
        "сон",
        "food",
        "nutrition",
        "calories",
        "protein",
        "diet",
        "fitness",
        "meal",
        "weight"
    ]

    lower_question = question.lower()

    is_allowed = any(topic in lower_question for topic in allowed_topics)

    if not is_allowed:
        return jsonify({
            "answer": "Я консультирую только по вопросам здорового питания, похудения, КБЖУ, спорта и здорового образа жизни 😊"
        })

    last_analysis = session.get("last_analysis", "")
    history = session.get("chat_history", [])

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        if last_analysis:
            messages.append({
                "role": "system",
                "content": f"Последний анализ еды:\n{last_analysis}"
            })

        messages.extend(history)
        messages.append({"role": "user", "content": question})

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_completion_tokens=700
        )

        answer = response.choices[0].message.content.strip()

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        session["chat_history"] = history[-10:]

        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"answer": f"❌ Ошибка: {str(e)}"})


if __name__ == "__main__":
    print("Сайт запущен:")
    print("http://127.0.0.1:5000/")
    app.run(host="0.0.0.0", port=5000, debug=True)