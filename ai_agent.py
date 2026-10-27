import ollama


def analyze_complaint(description):

    prompt = f"""
You are an AI assistant for a police complaint management system.

Analyze the following citizen complaint.

Complaint:
{description}

Identify:
1. Crime Type
2. Urgency Level (Low, Medium, or High)
3. Short Reason

Give the answer in this format:

Crime Type: ...
Urgency: ...
Reason: ...
"""

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]