
import json
import os

# Load external keyword mappings
KEYWORD_FILE = os.path.join(os.path.dirname(__file__), "persona_keywords.json")
try:
    with open(KEYWORD_FILE, "r", encoding="utf-8") as f:
        CUSTOM_KEYWORDS = json.load(f)
except Exception as e:
    print(f"⚠️ Failed to load persona_keywords.json: {e}")
    CUSTOM_KEYWORDS = {}

def match_persona(bio: str) -> str:
    bio_lower = bio.lower()
    for persona, keywords in CUSTOM_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in bio_lower:
                return persona
    return "default"


PERSONAS = {
    "fitness": {
        "keywords": ["fitness", "personal trainer", "coach", "gym", "strength", "nutrition", "training", "workout", "wellness", "weight loss"],
        "template": "Hey {name}, I love your work in the fitness space! Always looking to connect with like-minded trainers and enthusiasts."
    },
    "tech": {
        "keywords": ["developer", "engineer", "programmer", "coding", "software", "startup", "tech", "SaaS", "cloud", "AI", "ML", "data"],
        "template": "Hi {name}, I came across your profile in the tech scene. Would love to connect and share ideas in the space!"
    },
    "business": {
        "keywords": ["entrepreneur", "founder", "CEO", "marketing", "consultant", "business", "strategy", "growth", "coach", "branding"],
        "template": "Hi {name}, I’m always networking with other business professionals — your profile stood out. Let’s connect!"
    },
    "healthcare": {
        "keywords": ["doctor", "nurse", "therapist", "healthcare", "mental health", "wellness", "clinic", "hospital"],
        "template": "Hey {name}, your work in healthcare is inspiring! Let’s connect and share insights on promoting wellness."
    },
    "fitness_coach": {
        "keywords": ["fitness", "personal trainer", "gym", "workout", "strength", "coach", "wellness"],
        "template": "Hi {name}, love what you're doing in the fitness world! I specialize in tools that help coaches like you scale outreach. Let me know if you'd be open to a quick chat!"
    },
    "nutritionist": {
        "keywords": ["nutrition", "dietitian", "health coach", "meal plan", "holistic", "wellness", "clean eating"],
        "template": "Hi {name}, your passion for nutrition really stands out. I’d love to share something that can help nutrition professionals like you reach more clients effortlessly!"
    },
    "entrepreneur": {
        "keywords": ["founder", "CEO", "startup", "business owner", "entrepreneur", "SaaS", "growth"],
        "template": "Hi {name}, it's always inspiring to see founders doing impactful work. I help entrepreneurs like you save hours on outreach with a smart automation toolkit."
    },
    "influencer": {
        "keywords": ["influencer", "creator", "content", "brand deals", "collab", "ambassador"],
        "template": "Hey {name}, love your content! I work with creators to streamline their lead gen and brand partnership outreach. Would love to connect!"
    },
    "financial_professional": {
        "keywords": ["financial advisor", "wealth manager", "investment advisor", "retirement planning", "certified planner"],
        "template": "Hi {name}, I admire your work in financial planning. I’ve helped others in the finance sector connect with more qualified leads through automation tools. Let’s connect!"
    },
    "stock_trader": {
        "keywords": ["stock trader", "day trader", "swing trader", "equities", "options trading"],
        "template": "Hi {name}, I noticed you're active in the stock market space. I’d love to share a tool that helps traders like you generate targeted leads and expand your reach."
    },
    "crypto_investor": {
        "keywords": ["crypto", "blockchain", "bitcoin", "ethereum", "NFT", "DeFi", "web3", "crypto trader"],
        "template": "Hey {name}, always great to connect with fellow crypto enthusiasts. I work on tools that help crypto pros like you grow your audience with less manual effort. Interested?"
    },
    "travel_transport": {
        "keywords": ["travel agent", "luxury travel", "tour guide", "transportation", "chauffeur", "pilot", "private jet", "van life"],
        "template": "Hi {name}, your work in the travel industry caught my eye! We’re building smart outreach systems for professionals in travel and transport—happy to connect!"
    },
    "default": {
        "keywords": [],
        "template": "Hi {name}, just reaching out to connect with like-minded professionals. Looking forward to staying in touch!"
    },
    "ecommerce": {
    "style": "friendly and entrepreneurial",
    "tone": "growth-focused",
    "goal": "connect over online selling, growth hacks, or product scaling",
    "examples": [
        "Hi {name}, always great to meet fellow e-commerce builders — your profile stood out! Let’s connect and share insights.",
        "Hey {name}, love seeing e-commerce innovators pushing boundaries. Looking forward to learning from each other!"
        ]
    },
    "retail": {
    "style": "engaging and practical",
    "tone": "consumer-savvy",
    "goal": "connect over customer experience, store strategy, or product trends",
    "examples": [
        "Hi {name}, your retail work caught my eye — especially in today’s fast-shifting consumer space. Let’s connect!",
        "Hey {name}, looks like you're making moves in retail! Would enjoy chatting about product trends and retail tech."
        ]
    },
    "real_estate": {
    "style": "warm and professional",
    "tone": "trust-building",
    "goal": "spark a conversation about real estate trends, buying/selling, or investment",
    "examples": [
        "Hi {name}, I came across your profile and love your approach to real estate. Always excited to connect with professionals shaping the housing market!",
        "Hi {name}, your real estate insights stood out — would love to connect and exchange perspectives on today's property trends."
        ]
    },

}

if __name__ == "__main__":
    print(PERSONAS.keys())