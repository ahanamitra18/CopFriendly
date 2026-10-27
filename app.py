
import os
from dotenv import load_dotenv

from flask import Flask, render_template, request, session, redirect, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from ai_agent import analyze_complaint
from html import escape
from police_ai_agent import ask_police_ai

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
from functools import wraps

def police_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "police_id" not in session:
            return redirect(url_for("police_login"))
        return view_function(*args, **kwargs)
    return wrapped_view


# ---------------- DATABASE CONNECTION ----------------

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("home.html")


# ---------------- CITIZEN PORTAL ----------------

@app.route("/citizen")
def citizen():
    return render_template("citizen.html")


# ---------------- CITIZEN REGISTRATION ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")

        if not name or not email or not password:
            return "Please fill in all required fields."

        # Hash the password before storing it.
        hashed_password = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO citizens
                (name, email, phone, password)
                VALUES (%s, %s, %s, %s)
                """,
                (name, email, phone, hashed_password)
            )

            connection.commit()
            return "Registration successful!"

        except mysql.connector.Error as error:
            connection.rollback()
            print("Registration error:", error)
            return (
                "Registration failed. Check the details "
                "or try using another email."
            )

        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")


# ---------------- CITIZEN LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            return "Please enter your email and password."

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT citizen_id, name, password
                FROM citizens
                WHERE email = %s
                """,
                (email,)
            )

            citizen_record = cursor.fetchone()

        finally:
            cursor.close()
            connection.close()

        # Verify the submitted password against the stored hash.
        if citizen_record and check_password_hash(
            citizen_record[2], password
        ):
            session["citizen_id"] = citizen_record[0]
            session["citizen_name"] = citizen_record[1]

            return (
                "Login successful! Welcome "
                + escape(citizen_record[1])
                + '. <a href="/citizen">Go to Citizen Portal</a>'
            )

        return "Invalid email or password!"

    return render_template("login.html")


# ---------------- POLICE DASHBOARD ----------------

@app.route("/police/login", methods=["GET", "POST"])
def police_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            return "Please enter your email and password."

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT police_id, name, password
                FROM police
                WHERE email = %s
                """,
                (email,)
            )
            officer = cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

        if officer and check_password_hash(officer[2], password):
            session["police_id"] = officer[0]
            session["police_name"] = officer[1]

            return (
                "Police login successful! Welcome "
                + escape(officer[1])
                + '. <a href="/police">Open Police Dashboard</a>'
            )

        return "Invalid email or password!"

    return render_template("police_login.html")
@app.route("/police/logout")
def police_logout():
    session.pop("police_id", None)
    session.pop("police_name", None)
    return redirect(url_for("police_login"))
@app.route("/police")
@police_required
def police():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM complaints")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM complaints WHERE status = 'Pending'"
        )
        pending = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'"
        )
        in_progress = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'"
        )
        resolved = cursor.fetchone()[0]

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "police.html",
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved
    )


# ---------------- COMPLAINT SUBMISSION + AI ANALYSIS ----------------

@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    if "citizen_id" not in session:
        return "Please login first!"

    if request.method == "POST":
        complaint_type = request.form.get("complaint_type")
        location = request.form.get("location")
        description = request.form.get("description")

        if not complaint_type or not location or not description:
            return "Please fill in all complaint fields."

        citizen_id = session["citizen_id"]

        # Analyze the complaint using the local AI model.
        try:
            ai_analysis = analyze_complaint(description)
        except Exception as error:
            print("AI analysis failed:", error)
            ai_analysis = (
                "AI analysis is currently unavailable. "
                "Your complaint can still be submitted."
            )

        ai_crime_type = None
        ai_urgency = None
        ai_reason = None

        for line in ai_analysis.splitlines():
            if line.lower().startswith("crime type:"):
                ai_crime_type = line.split(":", 1)[1].strip()
            elif line.lower().startswith("urgency:"):
                ai_urgency = line.split(":", 1)[1].strip()
            elif line.lower().startswith("reason:"):
                ai_reason = line.split(":", 1)[1].strip()

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO complaints
                (
                    citizen_id,
                    complaint_type,
                    location,
                    description,
                    ai_crime_type,
                    ai_urgency,
                    ai_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    citizen_id,
                    complaint_type,
                    location,
                    description,
                    ai_crime_type,
                    ai_urgency,
                    ai_reason
                )
            )

            connection.commit()
            complaint_id = cursor.lastrowid

        except mysql.connector.Error as error:
            connection.rollback()
            print("Complaint submission error:", error)
            return "Unable to submit your complaint. Please try again."

        finally:
            cursor.close()
            connection.close()

        return (
            "<!DOCTYPE html>"
            "<html><head><meta charset='UTF-8'>"
            "<title>Complaint Submitted - Cop Friendly</title>"
            "</head><body>"
            "<h1>Complaint Submitted Successfully!</h1>"
            f"<p>Your complaint ID is #{complaint_id}.</p>"
            "<h2>AI Complaint Analysis</h2>"
            f"<pre style='white-space: pre-wrap;'>{escape(ai_analysis)}</pre>"
            "<p><strong>Note:</strong> AI-generated results are suggestions "
            "and should be verified by authorized personnel.</p>"
            '<a href="/citizen">Back to Citizen Portal</a>'
            "</body></html>"
        )

    return render_template("complaint.html")


# ---------------- TRACK COMPLAINTS ----------------

@app.route("/track", methods=["GET", "POST"])
def track():
    if "citizen_id" not in session:
        return "Please login first!"

    if request.method == "POST":
        citizen_id = session["citizen_id"]

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    complaint_id,
                    complaint_type,
                    location,
                    description,
                    status,
                    created_at
                FROM complaints
                WHERE citizen_id = %s
                ORDER BY created_at DESC
                """,
                (citizen_id,)
            )
            complaints = cursor.fetchall()

        finally:
            cursor.close()
            connection.close()

        return render_template(
            "track_result.html",
            complaints=complaints
        )

    return render_template("track_complaint.html")


# ---------------- EMERGENCY PAGE ----------------

@app.route("/emergency")
def emergency():
    return render_template("emergency.html")


# ---------------- VIEW ALL POLICE COMPLAINTS ----------------

@app.route("/police/complaints")
@police_required
def police_complaints():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                complaints.complaint_id,
                citizens.name,
                complaints.complaint_type,
                complaints.location,
                complaints.description,
                complaints.status,
                police.name,
                complaints.ai_crime_type,
                complaints.ai_urgency,
                complaints.ai_reason
            FROM complaints
            JOIN citizens
                ON complaints.citizen_id = citizens.citizen_id
            LEFT JOIN police
                ON complaints.police_id = police.police_id
            ORDER BY complaints.created_at DESC
            """
        )
        complaints = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "police_complaints.html",
        complaints=complaints
    )


# ---------------- UPDATE COMPLAINT STATUS ----------------

@app.route("/police/update", methods=["GET", "POST"])
@police_required
def update_complaint():
    if request.method == "POST":
        complaint_id = request.form.get("complaint_id")
        status = request.form.get("status")

        if not complaint_id or status not in [
            "Pending", "In Progress", "Resolved"
        ]:
            return "Invalid complaint ID or status."

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                UPDATE complaints
                SET status = %s
                WHERE complaint_id = %s
                """,
                (status, complaint_id)
            )

            if cursor.rowcount == 0:
                connection.rollback()
                return "Complaint not found or status unchanged."

            connection.commit()
            return "Complaint status updated successfully!"

        except mysql.connector.Error as error:
            connection.rollback()
            print("Status update error:", error)
            return "Unable to update complaint status."

        finally:
            cursor.close()
            connection.close()

    return render_template("update_complaint.html")


# ---------------- POLICE ANALYTICS ----------------

@app.route("/police/analytics")
@police_required
def police_analytics():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*),
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END)
            FROM complaints
            """
        )
        summary = cursor.fetchone()

        total_complaints = summary[0] or 0
        pending_complaints = summary[1] or 0
        resolved_complaints = summary[2] or 0

        cursor.execute(
            """
            SELECT complaint_type, COUNT(*)
            FROM complaints
            GROUP BY complaint_type
            ORDER BY COUNT(*) DESC
            """
        )
        analytics = cursor.fetchall()

        cursor.execute(
            """
            SELECT status, COUNT(*)
            FROM complaints
            GROUP BY status
            ORDER BY COUNT(*) DESC
            """
        )
        status_analytics = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "police_analytics.html",
        analytics=analytics,
        status_analytics=status_analytics,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        resolved_complaints=resolved_complaints
    )


# ---------------- POLICE AI ASSISTANT ----------------

@app.route("/police/ai", methods=["GET", "POST"])
def police_ai():
    question = ""
    answer = ""

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if not question:
            answer = "Please enter a question."
        else:
            try:
                answer = ask_police_ai(question)
            except Exception as error:
                print("Police AI error:", error)
                answer = (
                    "Sorry, the AI assistant could not process "
                    "your question. Please try again."
                )

    return render_template(
        "police_ai.html",
        question=question,
        answer=answer
    )


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=False)
