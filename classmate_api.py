
import os
import sqlite3
import requests

from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE = os.path.join(os.path.dirname(__file__), "classmate.db")

# CLASSMATE'S RENDER API
CLASSMATE_URL = "https://kleinjasperagrabio.onrender.com/course"
PARTNER_API_URL = CLASSMATE_URL + "/api/students"
COURSE_API_URL = CLASSMATE_URL + "/course"


# --------------------------------
# DATABASE CONNECTION
# --------------------------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------
# CREATE DATABASE TABLE
# --------------------------------

def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            program TEXT NOT NULL,
            year INTEGER NOT NULL,
            section TEXT NOT NULL,
            source TEXT DEFAULT 'Local'
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    if count == 0:
        students = [
            ("25-00101", "Alex Santos", "BSIT", 1, "A", "Local"),
            ("25-00102", "Maria Reyes", "BSIT", 2, "B", "Local"),
            ("25-00103", "Kevin Cruz", "BSIT", 3, "A", "Local"),
            ("25-00104", "Sophia Garcia", "BSIT", 2, "A", "Local"),
            ("25-00105", "Daniel Flores", "BSIT", 4, "B", "Local")
        ]

        conn.executemany("""
            INSERT INTO students
            (student_id, name, program, year, section, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, students)

    conn.commit()
    conn.close()


# --------------------------------
# HOME
# --------------------------------

@app.route("/")
def home():
    return jsonify({
        "message": "Classmate Student Integration API is running!",
        "classmate_url": CLASSMATE_URL,
        "endpoints": {
            "my_students": "GET /api/students",
            "add_student": "POST /api/students",
            "one_student": "GET /api/students/<id>",
            "partner_students": "GET /partner-records",
            "partner_course": "GET /partner-course",
            "health": "GET /health"
        }
    })


# --------------------------------
# GET ALL LOCAL STUDENTS
# --------------------------------

@app.route("/api/students", methods=["GET"])
def get_students():
    conn = get_db_connection()

    students = conn.execute("""
        SELECT * FROM students ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(student) for student in students])


# --------------------------------
# GET ONE STUDENT
# --------------------------------

@app.route("/api/students/<int:id>", methods=["GET"])
def get_student(id):
    conn = get_db_connection()

    student = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (id,)).fetchone()

    conn.close()

    if student is None:
        return jsonify({"error": "Student not found"}), 404

    return jsonify(dict(student))


# --------------------------------
# RECEIVE STUDENT RECORD
# --------------------------------

@app.route("/api/students", methods=["POST"])
def add_student():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON record is required"}), 400

    required_fields = [
        "student_id", "name", "program", "year", "section"
    ]

    for field in required_fields:
        if data.get(field) is None or str(data[field]).strip() == "":
            return jsonify({"error": f"Missing field: {field}"}), 400

    try:
        year = int(data["year"])
    except (ValueError, TypeError):
        return jsonify({"error": "Year must be a number"}), 400

    source = data.get("source", "External API")

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO students
        (student_id, name, program, year, section, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        str(data["student_id"]).strip(),
        str(data["name"]).strip(),
        str(data["program"]).strip(),
        year,
        str(data["section"]).strip(),
        source
    ))

    conn.commit()

    student = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (cursor.lastrowid,)).fetchone()

    conn.close()

    return jsonify({
        "message": "Student received successfully!",
        "student": dict(student)
    }), 201


# --------------------------------
# GET CLASSMATE'S STUDENT RECORDS
# --------------------------------

@app.route("/partner-records", methods=["GET"])
def partner_records():
    try:
        response = requests.get(PARTNER_API_URL, timeout=15)
        response.raise_for_status()

        return jsonify(response.json())

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to retrieve classmate records",
            "details": str(error)
        }), 502


# --------------------------------
# GET CLASSMATE'S COURSE INFORMATION
# --------------------------------

@app.route("/partner-course", methods=["GET"])
def partner_course():
    try:
        response = requests.get(COURSE_API_URL, timeout=15)
        response.raise_for_status()

        return jsonify(response.json())

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to retrieve classmate course information",
            "details": str(error)
        }), 502


# --------------------------------
# IMPORT CLASSMATE RECORD
# --------------------------------

@app.route("/import-student", methods=["POST"])
def import_student():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON record is required"}), 400

    required_fields = [
        "student_id", "name", "program", "year", "section"
    ]

    for field in required_fields:
        if data.get(field) is None or str(data[field]).strip() == "":
            return jsonify({"error": f"Missing field: {field}"}), 400

    try:
        year = int(data["year"])
    except (ValueError, TypeError):
        return jsonify({"error": "Year must be a number"}), 400

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO students
        (student_id, name, program, year, section, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        str(data["student_id"]).strip(),
        str(data["name"]).strip(),
        str(data["program"]).strip(),
        year,
        str(data["section"]).strip(),
        "Classmate API"
    ))

    conn.commit()

    student = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (cursor.lastrowid,)).fetchone()

    conn.close()

    return jsonify({
        "message": "Classmate record saved to your database!",
        "student": dict(student)
    }), 201


# --------------------------------
# SEND PRACTICE RECORD TO CLASSMATE
# --------------------------------

@app.route("/send-to-partner", methods=["POST"])
def send_to_partner():
    record = {
        "student_id": "EXT-001",
        "name": "Sample Exchange Record",
        "program": "BSIT",
        "year": 1,
        "section": "A",
        "source": "Partner API"
    }

    try:
        response = requests.post(
            PARTNER_API_URL,
            json=record,
            timeout=15
        )

        return jsonify({
            "message": "Partner API response received",
            "status_code": response.status_code,
            "response": response.text
        }), 200 if response.ok else 502

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to send record to classmate",
            "details": str(error)
        }), 502


# --------------------------------
# INTEGRATION DASHBOARD
# --------------------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    conn = get_db_connection()

    local = conn.execute("""
        SELECT COUNT(*) FROM students WHERE source = 'Local'
    """).fetchone()[0]

    imported = conn.execute("""
        SELECT COUNT(*) FROM students WHERE source = 'Classmate API'
    """).fetchone()[0]

    external = conn.execute("""
        SELECT COUNT(*) FROM students
        WHERE source IN ('External API', 'Partner API')
    """).fetchone()[0]

    total = conn.execute("""
        SELECT COUNT(*) FROM students
    """).fetchone()[0]

    conn.close()

    return jsonify({
        "total_records": total,
        "local_records": local,
        "imported_records": imported,
        "external_records": external
    })


# --------------------------------
# HEALTH CHECK
# --------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "Online",
        "message": "Classmate API is working!"
    })


# --------------------------------
# START APPLICATION
# --------------------------------

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
