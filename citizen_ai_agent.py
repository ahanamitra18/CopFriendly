
import ollama


def ask_citizen_ai(question):
    prompt = f"""
You are the Citizen Help Assistant for the Cop Friendly platform.

Actual platform features:
- Citizens can register and log in.
- Login is required before submitting a complaint.
- The complaint form requires three fields:
  1. Complaint type
  2. Location
  3. Description
- Successful submission generates a complaint ID.
- AI analyzes the complaint description and may provide crime type,
  urgency, and a reason.
- AI analysis is a suggestion that authorized personnel must verify.
- Citizens can track complaint status.

Instructions:
1. Answer in simple, polite, concise language.
2. Explain only the features listed above.
3. Never claim to submit a complaint or change its status.
4. Never invent form fields, URLs, or support contacts.
5. Never request passwords or OTPs.
6. For an immediate emergency in India, advise calling 112.
7. If you do not know an answer, say so.

Citizen's question:
{question}
"""

    try:
        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response["message"]["content"].strip()

    except Exception as error:
        print("Citizen chatbot Ollama error:", error)
        return (
            "Sorry, the chatbot is temporarily unavailable. "
            "Please try again later."
        )
