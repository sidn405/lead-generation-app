import random
from personas import PERSONAS, match_persona
import json
import os
import re
from json_utils import load_json_safe
# Import multilingual capabilities
try:
    from multilingual_dm_generator import (
        detect_user_language,
        generate_multilingual_dm,
        get_multilingual_prompt_modifier,
        get_multilingual_fallback
    )
    MULTILINGUAL_AVAILABLE = True
except ImportError:
    print("⚠️ Multilingual module not found. Using English-only mode.")
    MULTILINGUAL_AVAILABLE = False

# Platform-specific settings (enhanced with multilingual support)
PLATFORM_SETTINGS = {
    "twitter": {"max_length": 280, "style": "casual", "emojis": True},
    "linkedin": {"max_length": 300, "style": "professional", "emojis": False},
    "instagram": {"max_length": 200, "style": "casual", "emojis": True},
    "facebook": {"max_length": 250, "style": "casual", "emojis": True},
    "tiktok": {"max_length": 150, "style": "tiktok", "emojis": True},
    "youtube": {"max_length": 280, "style": "youtube", "emojis": True},
    "medium": {"max_length": 400, "style": "medium", "emojis": False},
    "reddit": {"max_length": 250, "style": "reddit", "emojis": False},
    "default": {"max_length": 200, "style": "professional", "emojis": False}
}

# Load keyword config once
try:
    with open("persona_keywords.json", "r") as f:
        PERSONA_KEYWORDS = load_json_safe(f)
except Exception as e:
    print(f"⚠️ Could not load persona_keywords.json: {e}")
    PERSONA_KEYWORDS = {}

def match_persona_from_bio(bio: str) -> str:
    bio_lower = bio.lower()
    for persona, data in PERSONAS.items():
        for keyword in data["keywords"]:
            if keyword.lower() in bio_lower:
                return persona
    return "default"

def get_platform_prompt_modifier(platform: str, language: str = "english") -> str:
    """Get platform-specific prompt instructions for OpenAI (now with language support)"""
    
    if MULTILINGUAL_AVAILABLE and language != "english":
        return get_multilingual_prompt_modifier(platform, language, "default")
    
    # Original English modifiers
    modifiers = {
        "tiktok": "Make the message ultra-casual, fun, and include relevant emojis. Keep it short and engaging for a young audience. Use words like 'yo', 'fire', 'collab'.",
        "youtube": "Focus on creator collaboration and networking. Mention their content/channel positively. Use terms like 'subscribe', 'content', 'collaborate'.",
        "medium": "Write in a professional, intellectual tone. Focus on their writing and insights. Be thoughtful and respectful. No emojis.",
        "reddit": "Be direct and authentic. No emojis or overly casual language. Sound genuine and community-minded. Mention their posts/contributions.",
        "twitter": "Keep it casual and friendly with appropriate emojis.",
        "linkedin": "Maintain a professional networking tone without emojis.",
        "instagram": "Use a casual, visual-focused approach with emojis.",
        "facebook": "Be friendly and approachable with light emoji use."
    }
    return modifiers.get(platform, "Write a friendly professional message.")

def apply_platform_filters(message: str, platform: str) -> str:
    """Apply platform-specific formatting and length limits"""
    settings = PLATFORM_SETTINGS.get(platform, PLATFORM_SETTINGS["default"])
    
    # Remove emojis if platform doesn't support them
    if not settings["emojis"]:
        message = re.sub(r'[^\w\s!?.,\'-]', '', message)
    
    # Enforce character limits
    if len(message) > settings["max_length"]:
        message = message[:settings["max_length"]-3] + "..."
    
    return message.strip()

def initialize_openai_client():
    """Initialize OpenAI client based on available version"""
    try:
        # Try new OpenAI v1.x.x first
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ OPENAI_API_KEY not found in environment variables")
            return None, "v1"
        
        client = OpenAI(api_key=api_key)
        return client, "v1"
        
    except ImportError:
        try:
            # Fall back to old OpenAI v0.x.x
            import openai
            openai.api_key = os.getenv("OPENAI_API_KEY")
            return openai, "v0"
        except ImportError:
            print("⚠️ OpenAI library not found")
            return None, None

def generate_dm_with_openai_v1(client, messages, model="gpt-4o-mini", temperature=0.7, max_tokens=200):
    """Generate DM using OpenAI v1.x.x"""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()

def generate_dm_with_openai_v0(openai_module, messages, model="gpt-4o-mini", temperature=0.7, max_tokens=200):
    """Generate DM using OpenAI v0.x.x"""
    response = openai_module.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()

def get_platform_fallback(name: str, platform: str, language: str = "english") -> str:
    """Get platform-specific fallback messages (now with language support)"""
    
    if MULTILINGUAL_AVAILABLE and language != "english":
        return get_multilingual_fallback(name, platform, language)
    
    # Original English fallbacks
    first_name = name.split()[0] if name else "there"
    
    fallbacks = {
        "tiktok": f"Yo {first_name}! Love your content! Let's connect! 🔥",
        "youtube": f"Hey {first_name}! Love your channel! Would love to collaborate sometime!",
        "medium": f"Hello {first_name}, I enjoyed your writing and would love to connect for future discussions.",
        "reddit": f"Hey {first_name}, saw your posts and thought they were insightful. Mind if we connect?",
        "twitter": f"Hi {first_name}, just reaching out to connect with like-minded professionals!",
        "linkedin": f"Hi {first_name}, would love to connect and expand my professional network.",
        "instagram": f"Hey {first_name}! Love your content! Let's connect! ✨",
        "facebook": f"Hi {first_name}! Hope you're doing well. Would love to connect!"
    }
    
    return fallbacks.get(platform, f"Hi {first_name}, just reaching out to connect with like-minded professionals on {platform.capitalize()}!")

def generate_dm_with_fallback(name: str, bio: str, platform: str, language: str = None, auto_detect_language: bool = True) -> str:
    """
    Generate personalized DM with automatic fallback - Enhanced with multilingual support
    
    Args:
        name: Full name of the person
        bio: Bio/description text
        platform: Platform name
        language: Target language (None for auto-detection)
        auto_detect_language: Whether to auto-detect language from bio/name
    """
    
    # Auto-detect language if enabled and not specified
    if auto_detect_language and language is None and MULTILINGUAL_AVAILABLE:
        language = detect_user_language(name, bio, platform)
        print(f"🌍 Auto-detected language: {language}")
    elif language is None:
        language = "english"
    
    # Use multilingual generation if available and not English
    if MULTILINGUAL_AVAILABLE and language != "english":
        print(f"🌍 Using multilingual generation for {language}")
        result = generate_multilingual_dm(name, bio, platform, language)
        return result["dm"]
    
    # Original English generation logic
    persona = match_persona(bio)
    profile_data = PERSONAS.get(persona, PERSONAS["default"])
    
    # Build base prompt
    if "template" in profile_data:
        base_prompt = profile_data["template"].format(
            name=name.split()[0],
            platform=platform.capitalize(),
            bio=bio.strip()
        )
    elif "examples" in profile_data:
        base_prompt = profile_data["examples"][0].format(name=name.split()[0])
    else:
        base_prompt = PERSONAS["default"]["template"].format(
            name=name.split()[0],
            platform=platform.capitalize(),
            bio=bio.strip()
        )
    
    # Add platform-specific instructions
    platform_modifier = get_platform_prompt_modifier(platform, language)
    enhanced_prompt = f"{base_prompt}\n\nPlatform-specific instructions: {platform_modifier}"
    
    print(f"🧠 Using persona: {persona} for {platform} in {language}")
    
    # Try OpenAI API
    client, version = initialize_openai_client()
    
    if client is None:
        print("⚠️ OpenAI not available, using platform-specific fallback")
        return get_platform_fallback(name, platform, language)
    
    try:
        messages = [
            {"role": "system", "content": f"You're a social media outreach assistant skilled at writing platform-specific DMs. Adapt your writing style to {platform} culture and audience expectations."},
            {"role": "user", "content": enhanced_prompt}
        ]
        
        if version == "v1":
            raw_message = generate_dm_with_openai_v1(client, messages)
        elif version == "v0":
            raw_message = generate_dm_with_openai_v0(client, messages)
        else:
            raise Exception("Unknown OpenAI version")
        
        # Apply platform-specific filters
        final_message = apply_platform_filters(raw_message, platform)
        return final_message
            
    except Exception as e:
        print(f"⚠️ GPT API error: {e}")
        print(f"   Using platform-specific fallback instead")
        return get_platform_fallback(name, platform, language)

def test_openai_setup():
    """Test OpenAI setup and return status"""
    client, version = initialize_openai_client()
    
    if client is None:
        return False, "OpenAI client could not be initialized"
    
    try:
        # Test with a simple message
        test_messages = [
            {"role": "user", "content": "Say 'test successful' if you can read this."}
        ]
        
        if version == "v1":
            response = generate_dm_with_openai_v1(client, test_messages, max_tokens=10)
        else:
            response = generate_dm_with_openai_v0(client, test_messages, max_tokens=10)
            
        return True, f"OpenAI {version} working. Test response: {response}"
        
    except Exception as e:
        return False, f"OpenAI {version} error: {str(e)}"

def generate_multiple_dms(contacts: list, platform: str = "twitter", language: str = None, auto_detect_language: bool = True) -> list:
    """
    Generate DMs for multiple contacts - Enhanced with multilingual support
    
    Args:
        contacts: list of dicts with 'name' and 'bio' keys
        platform: target platform
        language: target language (None for auto-detection)
        auto_detect_language: whether to auto-detect language per contact
    """
    results = []
    
    print(f"🚀 Generating DMs for {platform}...")
    if language:
        print(f"🌍 Target language: {language}")
    elif auto_detect_language:
        print(f"🌍 Auto-detecting language per contact")
    
    for contact in contacts:
        try:
            # Determine language for this contact
            contact_language = language
            if auto_detect_language and language is None and MULTILINGUAL_AVAILABLE:
                contact_language = detect_user_language(
                    contact.get("name", ""), 
                    contact.get("bio", ""), 
                    platform
                )
            
            dm = generate_dm_with_fallback(
                name=contact.get("name", "Friend"),
                bio=contact.get("bio", ""),
                platform=platform,
                language=contact_language,
                auto_detect_language=False  # We already detected it
            )
            
            results.append({
                "name": contact.get("name"),
                "bio": contact.get("bio"),
                "dm": dm,
                "persona": match_persona(contact.get("bio", "")),
                "platform": platform,
                "language": contact_language or "english",
                "length": len(dm)
            })
            
        except Exception as e:
            print(f"⚠️ Error generating DM for {contact.get('name')}: {e}")
            fallback_language = language or "english"
            fallback_dm = get_platform_fallback(contact.get("name", "there"), platform, fallback_language)
            
            results.append({
                "name": contact.get("name"),
                "bio": contact.get("bio"),
                "dm": fallback_dm,
                "persona": "fallback",
                "platform": platform,
                "language": fallback_language,
                "length": len(fallback_dm),
                "error": str(e)
            })
    
    return results

def test_multilingual_features():
    """Test the multilingual capabilities"""
    
    if not MULTILINGUAL_AVAILABLE:
        print("❌ Multilingual features not available. Install multilingual_dm_generator.py")
        return
    
    print("🌍 Testing Multilingual Features")
    print("=" * 40)
    
    # Test contacts with different languages
    test_contacts = [
        {"name": "José García", "bio": "Entrenador de fitness en Madrid"},
        {"name": "Marie Dubois", "bio": "Créatrice de contenu beauté"},
        {"name": "Hans Mueller", "bio": "Software-Entwickler in Berlin"},
        {"name": "John Smith", "bio": "Tech entrepreneur in Silicon Valley"}
    ]
    
    platforms = ["twitter", "linkedin"]
    
    for platform in platforms:
        print(f"\n📱 Testing {platform.upper()} with auto-detection:")
        print("-" * 45)
        
        results = generate_multiple_dms(test_contacts, platform, auto_detect_language=True)
        
        for result in results:
            print(f"👤 {result['name']} ({result['language']}):")
            print(f"💬 {result['dm']}")
            print(f"🎭 Persona: {result['persona']}")
            print()

def test_all_platforms_multilingual():
    """Test multilingual generation across all supported platforms"""
    
    if not MULTILINGUAL_AVAILABLE:
        print("❌ Multilingual features not available")
        return "Multilingual not available"
    
    # Import multilingual batch function
    from multilingual_dm_generator import generate_multilingual_batch
    
    test_contacts = [
        {"name": "María López", "bio": "Influencer de moda en Instagram"},
        {"name": "Pierre Martin", "bio": "Chef et créateur de contenu culinaire"},
        {"name": "Klaus Weber", "bio": "Tech-YouTuber aus München"}
    ]
    
    platforms = ["tiktok", "youtube", "medium", "reddit", "twitter", "linkedin"]
    
    print("🌍 Testing Multilingual Generation Across All Platforms")
    print("=" * 60)
    
    for platform in platforms:
        print(f"\n📱 {platform.upper()} Results:")
        print("-" * 30)
        
        results = generate_multilingual_batch(test_contacts, platform)
        
        for result in results:
            print(f"👤 {result['original_name']} ({result['detected_language']}):")
            print(f"💬 {result['dm']}")
            print(f"📏 {result['length']} chars | 🎭 {result['persona']}")
            print()
    
    return "✅ All multilingual platforms tested successfully!"

# Backward compatibility function
def generate_dm_with_fallback_simple(name: str, bio: str, platform: str = "twitter") -> str:
    """Simplified version for backward compatibility (now with auto-language detection)"""
    return generate_dm_with_fallback(name, bio, platform, auto_detect_language=True)

if __name__ == "__main__":
    print("🧪 Testing Enhanced DM Sequences with Multilingual Support")
    print("=" * 65)
    
    # Test basic functionality
    print("\n1. Testing basic functionality...")
    test_openai_setup()
    
    # Test multilingual features if available
    print("\n2. Testing multilingual features...")
    test_multilingual_features()
    
    # Test all platforms with multilingual
    print("\n3. Testing all platforms with multilingual...")
    test_all_platforms_multilingual()