
import openai
import os
from personas import PERSONAS  # stored in a separate file for cleaner management

openai.api_key = os.getenv("OPENAI_API_KEY")  # Make sure this is set in your .env or system

def detect_persona(bio: str):
    bio_lower = bio.lower()
    for persona, data in PERSONAS.items():
        if any(keyword in bio_lower for keyword in data["keywords"]):
            return persona
    return "default"

def generate_dm(bio: str, name: str = None):
    persona = detect_persona(bio)
    prompt = PERSONAS[persona]["prompt"]
    
    full_prompt = f"{prompt}\n\nName: {name or 'Lead'}\nBio: {bio}\nDM:"
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": full_prompt}],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"⚠️ GPT DM generation failed: {e}")
        return "Hi there! Just reaching out to connect with like-minded professionals."

def generate_gpt_intro(lead: dict) -> str:
    # Fallbacks
    name = lead.get("name") or "there"
    platform = lead.get("platform") or "social media"
    bio = lead.get("bio") or "a professional in your field"

    # Prompt to GPT
    prompt = f"""
You are a friendly marketing assistant. Write a short, personalized DM (under 40 words) to someone named {name} on {platform}.
Base it on their bio: "{bio}".
Keep it casual, human-sounding, and relevant to their niche. Avoid sounding like a template or bot.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # You can swap to gpt-3.5-turbo to reduce cost
            messages=[
                {"role": "system", "content": "You are a helpful outreach assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=60,
            temperature=0.75
        )
        return response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"❌ GPT Error: {e}")
        return f"Hi {name}, just wanted to connect with like-minded folks on {platform}!"