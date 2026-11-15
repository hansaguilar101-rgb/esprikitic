
import os
import sqlite3
import requests

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# -----------------------------------------
# DATABASE AND PARTNER API CONFIGURATION
# -----------------------------------------

DATABASE = os.path.join(os.path.dirname(__file__), "students.db")

PARTNER_API_URL = os.environ.get(
    "PARTNER_API_URL",
    "https://kleinjasperagrabio.onrender.com/api/students"
)


# -----------------------------------------
# DATABASE CONNECTION
# -----------------------------------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------------------
# DATABASE SETUP
# -----------------------------------------

def setup_database():
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

    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(students)").fetchall()
    ]

    if "source" not in columns:
        conn.execute("""
            ALTER TABLE students
            ADD COLUMN source TEXT DEFAULT 'Local'
        """)

    conn.execute("""
        UPDATE students
        SET source = 'Local'
        WHERE source IS NULL OR TRIM(source) = ''
    """)

    conn.commit()
    conn.close()


# -----------------------------------------
# VALIDATE STUDENT DATA
# -----------------------------------------

def validate_student(data):
    required_fields = [
        "student_id",
        "name",
        "program",
        "year",
        "section"
    ]

    for field in required_fields:
        if data.get(field) is None or str(data.get(field)).strip() == "":
            return None, f"Missing required field: {field}"

    try:
        year = int(data["year"])
    except (ValueError, TypeError):
        return None, "Year must be a valid number."

    student = {
        "student_id": str(data["student_id"]).strip(),
        "name": str(data["name"]).strip(),
        "program": str(data["program"]).strip(),
        "year": year,
        "section": str(data["section"]).strip()
    }

    return student, None


# -----------------------------------------
# GET PARTNER RECORDS
# -----------------------------------------

def get_partner_records():
    response = requests.get(PARTNER_API_URL, timeout=15)
    response.raise_for_status()

    records = response.json()

    if isinstance(records, dict):
        records = records.get("students", [])

    if not isinstance(records, list):
        raise ValueError("Partner API did not return a list of students.")

    return records


# -----------------------------------------
# HOME PAGE
# -----------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------------------
# GET ALL STUDENTS
# -----------------------------------------

@app.route("/api/students", methods=["GET"])
def get_students():
    conn = get_db_connection()

    students = conn.execute("""
        SELECT * FROM students
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(student) for student in students])


# -----------------------------------------
# ADD STUDENT
# -----------------------------------------

@app.route("/api/students", methods=["POST"])
def add_student():
    data = request.get_json(silent=True) or {}

    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    source = data.get("source", "External API")

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO students
        (student_id, name, program, year, section, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        student["student_id"],
        student["name"],
        student["program"],
        student["year"],
        student["section"],
        source
    ))

    conn.commit()
    new_id = cursor.lastrowid

    saved_student = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (new_id,)).fetchone()

    conn.close()

    return jsonify({
        "message": "Student added successfully!",
        "student": dict(saved_student)
    }), 201


# -----------------------------------------
# GET ONE STUDENT
# -----------------------------------------

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


# -----------------------------------------
# UPDATE STUDENT
# -----------------------------------------

@app.route("/api/students/<int:id>", methods=["PUT"])
def update_student(id):
    data = request.get_json(silent=True) or {}

    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()

    existing = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (id,)).fetchone()

    if existing is None:
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    conn.execute("""
        UPDATE students
        SET student_id = ?,
            name = ?,
            program = ?,
            year = ?,
            section = ?
        WHERE id = ?
    """, (
        student["student_id"],
        student["name"],
        student["program"],
        student["year"],
        student["section"],
        id
    ))

    conn.commit()

    updated_student = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (id,)).fetchone()

    conn.close()

    return jsonify({
        "message": "Student updated successfully!",
        "student": dict(updated_student)
    })


# -----------------------------------------
# DELETE STUDENT
# -----------------------------------------

@app.route("/api/students/<int:id>", methods=["DELETE"])
def delete_student(id):
    conn = get_db_connection()

    existing = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (id,)).fetchone()

    if existing is None:
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    conn.execute("""
        DELETE FROM students WHERE id = ?
    """, (id,))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Student deleted successfully!"
    })


# -----------------------------------------
# STEP 3: RETRIEVE PARTNER RECORDS
# -----------------------------------------

@app.route("/partner-records", methods=["GET"])
def partner_records():
    try:
        records = get_partner_records()
        return jsonify(records)

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to retrieve partner data",
            "details": str(error)
        }), 502

    except (ValueError, TypeError) as error:
        return jsonify({
            "error": str(error)
        }), 502


# -----------------------------------------
# STEP 5: IMPORT PARTNER RECORD
# -----------------------------------------

@app.route("/import-student", methods=["POST"])
def import_student():
    data = request.get_json(silent=True) or {}

    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO students
        (student_id, name, program, year, section, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        student["student_id"],
        student["name"],
        student["program"],
        student["year"],
        student["section"],
        "Classmate API"
    ))

    conn.commit()
    new_id = cursor.lastrowid

    saved_student = conn.execute("""
        SELECT * FROM students WHERE id = ?
    """, (new_id,)).fetchone()

    conn.close()

    return jsonify({
        "message": "Remote record saved successfully!",
        "student": dict(saved_student)
    }), 201


# -----------------------------------------
# STEP 9: SEND RECORD TO PARTNER
# -----------------------------------------

@app.route("/send-to-partner", methods=["POST"])
def send_to_partner():
    data = request.get_json(silent=True) or {}

    if not data:
        data = {
            "student_id": "EXT-001",
            "name": "Sample Exchange Record",
            "program": "BSIT",
            "year": 1,
            "section": "A"
        }

    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    record = {
        **student,
        "source": "Partner API"
    }

    try:
        response = requests.post(
            PARTNER_API_URL,
            json=record,
            timeout=15
        )

        response.raise_for_status()

        try:
            partner_response = response.json()
        except ValueError:
            partner_response = response.text

        return jsonify({
            "message": "Record successfully sent to partner!",
            "partner_status": response.status_code,
            "partner_response": partner_response
        }), 200

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to send record to partner.",
            "details": str(error)
        }), 502


# -----------------------------------------
# INTEGRATION DASHBOARD
# -----------------------------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    conn = get_db_connection()

    local_records = conn.execute("""
        SELECT COUNT(*) FROM students
        WHERE source = 'Local'
    """).fetchone()[0]

    imported_records = conn.execute("""
        SELECT COUNT(*) FROM students
        WHERE source = 'Classmate API'
    """).fetchone()[0]

    external_records = conn.execute("""
        SELECT COUNT(*) FROM students
        WHERE source = 'External API'
           OR source = 'Partner API'
    """).fetchone()[0]

    total_records = conn.execute("""
        SELECT COUNT(*) FROM students
    """).fetchone()[0]

    conn.close()

    return jsonify({
        "total_records": total_records,
        "local_records": local_records,
        "imported_records": imported_records,
        "external_records": external_records
    })


# -----------------------------------------
# HEALTH CHECK
# -----------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "Online",
        "message": "Student Integration API is working!"
    })


# -----------------------------------------
# RUN APPLICATION
# -----------------------------------------

setup_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

