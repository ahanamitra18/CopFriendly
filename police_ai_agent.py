
import os
import mysql.connector
import ollama
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


def get_all_complaints():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT complaint_id, complaint_type, location,
                   description, status, created_at,
                   ai_crime_type, ai_urgency, ai_reason
            FROM complaints
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_high_urgency_complaints():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT complaint_id, complaint_type, location,
                   description, status, ai_crime_type,
                   ai_urgency, ai_reason
            FROM complaints
            WHERE ai_urgency = 'High'
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_status_counts():
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM complaints
            GROUP BY status
        """)
        counts = dict(cursor.fetchall())

        return {
            "Pending": counts.get("Pending", 0),
            "In Progress": counts.get("In Progress", 0),
            "Resolved": counts.get("Resolved", 0)
        }
    finally:
        cursor.close()
        connection.close()


def format_records(complaints):
    records = []

    for c in complaints:
        records.append(
            f"Complaint ID: {c['complaint_id']}\n"
            f"Complaint Type: {c['complaint_type']}\n"
            f"Location: {c['location']}\n"
            f"Description: {c['description']}\n"
            f"Status: {c['status']}\n"
            f"AI Crime Type: {c.get('ai_crime_type') or 'Not available'}\n"
            f"AI Urgency: {c.get('ai_urgency') or 'Not available'}\n"
            f"AI Reason: {c.get('ai_reason') or 'Not available'}"
        )

    return "\n\n".join(records)


def ask_police_ai(question):
    question_lower = question.lower()

    # Status counts must come directly from MySQL.
    if any(word in question_lower for word in [
        "how many", "count", "number of", "status summary",
        "complaint statistics", "complaint stats"
    ]) and any(word in question_lower for word in [
        "complaint", "pending", "resolved", "progress", "status"
    ]):
        counts = get_status_counts()
        total = sum(counts.values())

        return (
            "Current Complaint Status Summary\n\n"
            f"Total complaints: {total}\n"
            f"Pending: {counts['Pending']}\n"
            f"In Progress: {counts['In Progress']}\n"
            f"Resolved: {counts['Resolved']}\n\n"
            "These counts are retrieved directly from MySQL."
        )

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if (
            ("cyber crime" in question_lower
             or "cybercrime" in question_lower)
            and "pending" in question_lower
        ):
            cursor.execute("""
                SELECT complaint_id, complaint_type, location,
                       description, status, ai_crime_type,
                       ai_urgency, ai_reason
                FROM complaints
                WHERE status = 'Pending'
                  AND LOWER(complaint_type) LIKE '%cyber%'
                ORDER BY created_at DESC
            """)

        elif (
            "high urgency" in question_lower
            or "high-urgency" in question_lower
            or "urgent complaints" in question_lower
        ):
            cursor.execute("""
                SELECT complaint_id, complaint_type, location,
                       description, status, ai_crime_type,
                       ai_urgency, ai_reason
                FROM complaints
                WHERE ai_urgency = 'High'
                ORDER BY created_at DESC
            """)

        elif "pending" in question_lower:
            cursor.execute("""
                SELECT complaint_id, complaint_type, location,
                       description, status, ai_crime_type,
                       ai_urgency, ai_reason
                FROM complaints
                WHERE status = 'Pending'
                ORDER BY created_at DESC
            """)

        else:
            cursor.execute("""
                SELECT complaint_id, complaint_type, location,
                       description, status, ai_crime_type,
                       ai_urgency, ai_reason
                FROM complaints
                ORDER BY created_at DESC
            """)

        complaints = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    if not complaints:
        return "No complaints matched your question in the database."

    database_results = format_records(complaints)

    prompt = f"""
You are the Police AI Assistant for Cop Friendly.

Officer's question:
{question}

Verified MySQL records:
{database_results}

Instructions:
- Summarize only the supplied records.
- Do not invent complaints or change their statuses.
- Do not claim a status count unless it is directly supported by
  the supplied records.
- Treat AI urgency as a suggestion for human review.
- Keep the answer concise.
"""

    try:
        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[{"role": "user", "content": prompt}]
        )
        ai_summary = response["message"]["content"].strip()

    except Exception as error:
        print("Ollama error:", error)
        ai_summary = (
            "AI summary is unavailable. The database records "
            "retrieved for this question are shown below."
        )

    return (
        f"Found {len(complaints)} matching complaint(s).\n\n"
        f"AI Summary:\n{ai_summary}\n\n"
        f"Database Records:\n\n{database_results}"
    )
