
import mysql.connector
import ollama
import os
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


def ask_police_ai(question):
    """
    Retrieve complaint records from MySQL and generate
    a response using the local Ollama model.
    """

    question_lower = question.lower()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Pending cybercrime complaints
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

        # High-urgency complaints
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

        # All pending complaints
        elif "pending" in question_lower:
            cursor.execute("""
                SELECT complaint_id, complaint_type, location,
                       description, status, ai_crime_type,
                       ai_urgency, ai_reason
                FROM complaints
                WHERE status = 'Pending'
                ORDER BY created_at DESC
            """)

        # All complaints
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

    # Create a reliable list directly from the database records.
    complaint_list = []

    for complaint in complaints:
        complaint_list.append(
            f"Complaint ID: {complaint['complaint_id']}\n"
            f"Complaint Type: {complaint['complaint_type']}\n"
            f"Location: {complaint['location']}\n"
            f"Status: {complaint['status']}\n"
            f"Description: {complaint['description']}\n"
            f"AI Crime Type: {complaint['ai_crime_type'] or 'Not available'}\n"
            f"AI Urgency: {complaint['ai_urgency'] or 'Not available'}\n"
            f"AI Reason: {complaint['ai_reason'] or 'Not available'}"
        )

    database_results = "\n\n".join(complaint_list)

    # Ask the AI to summarize the retrieved records.
    prompt = f"""
You are the Police AI Assistant for the Cop Friendly platform.

Officer's question:
{question}

The following {len(complaints)} complaint record(s) were retrieved
from the MySQL database:

{database_results}

Instructions:
1. Summarize these records in clear, simple language.
2. Do not invent facts or complaint records.
3. Do not claim that records are missing unless the data shows that.
4. Treat AI-generated urgency as a suggestion requiring human review.
5. Keep the response concise.
"""

    try:
        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        ai_summary = response["message"]["content"].strip()

    except Exception as error:
        print("Ollama error:", error)
        ai_summary = "AI summary is temporarily unavailable."

    # Always append every database record so none are omitted.
    return (
        f"Found {len(complaints)} matching complaint(s).\n\n"
        f"AI Summary:\n{ai_summary}\n\n"
        f"Complete Database Records:\n\n{database_results}"
    )

