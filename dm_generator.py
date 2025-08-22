# dm_generator.py

import random
import json
import os

# Default DM templates by platform
DEFAULT_TEMPLATES = {
    "twitter": [
        "Hey {name}, loved your work on {topic}. Would love to connect!",
        "Hi {name}, came across your profile – very inspiring! Let's chat sometime."
    ],
    "linkedin": [
        "Hi {name}, your experience in {topic} really stood out. Would be great to connect!",
        "Hello {name}, I noticed your background in {topic} and thought we should network."
    ],
    "facebook": [
        "Hey {name}, I saw your profile and felt you’d be a great fit for something I’m working on.",
        "Hi {name}, your page caught my eye. Curious if you’re open to new opportunities!"
    ],
    "fallback": [
        "Hi! I hope this message finds you well. I'd love to connect if you're open to it.",
        "Hey there! Just reaching out to make a connection – let me know if you’re interested."
    ]
}

# Optional external override for templates
CUSTOM_TEMPLATE_FILE = "dm_templates.json"

def load_templates():
    if os.path.exists(CUSTOM_TEMPLATE_FILE):
        try:
            with open(CUSTOM_TEMPLATE_FILE, 'r') as f:
                templates = json.load(f)
                print("📥 Loaded custom DM templates.")
                return templates
        except Exception as e:
            print(f"⚠️ Error loading custom templates: {e}")
    return DEFAULT_TEMPLATES

TEMPLATES = load_templates()

def extract_topic_from_bio(bio):
    keywords = ['fitness', 'marketing', 'crypto', 'planner', 'designer', 'coach', 'developer']
    for word in keywords:
        if word.lower() in bio.lower():
            return word.capitalize()
    return None

def generate_dm(name=None, bio="", platform="twitter"):
    topic = extract_topic_from_bio(bio)
    name = name.strip() if name else "there"

    platform = platform.lower()
    if topic and platform in TEMPLATES:
        template = random.choice(TEMPLATES[platform])
        return template.format(name=name, topic=topic)
    else:
        return random.choice(TEMPLATES["fallback"]).format(name=name, topic="your field")