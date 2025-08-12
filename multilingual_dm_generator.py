#!/usr/bin/env python3
"""
Multilingual DM Generation System
Integrates with your existing dm_sequences.py and persona system
"""

import re
import random
from typing import Dict, List, Optional, Tuple

# Language detection keywords and patterns
LANGUAGE_KEYWORDS = {
    "english": {
        "keywords": ["the", "and", "is", "in", "to", "of", "it", "you", "that", "he", "was", "for", "on", "are", "as", "with", "his", "they", "at"],
        "greetings": ["Hi", "Hello", "Hey", "Greetings"],
        "connectors": ["I love", "I'm interested in", "I think it's great", "I'd love to"],
        "closings": ["Let's connect!", "Let's chat!", "Best regards!", "Talk soon!"]
    },
        "spanish": {
        "keywords": ["que", "con", "para", "por", "una", "como", "muy", "todo", "más", "hacer", "tiempo", "trabajo", "vida", "amor", "familia"],
        "greetings": ["¡Hola", "Hola", "¡Hey", "Saludos"],
        "connectors": ["Me encanta", "Me gusta", "Estoy interesado en", "Sería genial"],
        "closings": ["¡Conectemos!", "¡Hablemos!", "¡Saludos!", "¡Hasta pronto!"]
    },
    "french": {
        "keywords": ["que", "avec", "pour", "dans", "une", "comme", "très", "tout", "plus", "faire", "temps", "travail", "vie", "amour"],
        "greetings": ["Salut", "Bonjour", "Hey", "Coucou"],
        "connectors": ["J'adore", "J'aime", "Je suis intéressé par", "Ce serait génial"],
        "closings": ["Connectons-nous!", "Parlons!", "À bientôt!", "Salutations!"]
    },
    "german": {
        "keywords": ["und", "mit", "für", "auf", "eine", "wie", "sehr", "alle", "mehr", "machen", "zeit", "arbeit", "leben", "liebe"],
        "greetings": ["Hallo", "Hi", "Hey", "Grüß dich"],
        "connectors": ["Ich liebe", "Mir gefällt", "Ich interessiere mich für", "Das wäre toll"],
        "closings": ["Lass uns connecten!", "Lass uns sprechen!", "Bis bald!", "Grüße!"]
    },
    "portuguese": {
        "keywords": ["que", "com", "para", "por", "uma", "como", "muito", "todo", "mais", "fazer", "tempo", "trabalho", "vida", "amor"],
        "greetings": ["Oi", "Olá", "E aí", "Opa"],
        "connectors": ["Eu amo", "Eu gosto", "Estou interessado em", "Seria ótimo"],
        "closings": ["Vamos nos conectar!", "Vamos conversar!", "Até logo!", "Abraços!"]
    },
    "italian": {
        "keywords": ["che", "con", "per", "una", "come", "molto", "tutto", "più", "fare", "tempo", "lavoro", "vita", "amore"],
        "greetings": ["Ciao", "Salve", "Ehi", "Buongiorno"],
        "connectors": ["Amo", "Mi piace", "Sono interessato a", "Sarebbe fantastico"],
        "closings": ["Connettiamoci!", "Parliamo!", "A presto!", "Saluti!"]
    },
    "japanese": {
        "keywords": ["です", "ます", "こと", "もの", "ため", "について", "から", "まで", "という", "として"],
        "greetings": ["こんにちは", "はじめまして", "お疲れ様", "よろしく"],
        "connectors": ["大好きです", "興味があります", "素晴らしいと思います", "ぜひ"],
        "closings": ["つながりましょう！", "お話ししましょう！", "よろしくお願いします！", "また今度！"]
    },
    "korean": {
        "keywords": ["이", "가", "을", "를", "에", "에서", "와", "과", "로", "으로", "의", "도", "만", "부터"],
        "greetings": ["안녕하세요", "안녕", "반갑습니다", "처음 뵙겠습니다"],
        "connectors": ["좋아합니다", "관심이 있습니다", "훌륭하다고 생각합니다", "꼭"],
        "closings": ["연결해요!", "대화해요!", "감사합니다!", "또 만나요!"]
    },
    "chinese": {
        "keywords": ["的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "个", "会", "说"],
        "greetings": ["你好", "您好", "嗨", "大家好"],
        "connectors": ["我喜欢", "我对...感兴趣", "我觉得很棒", "很想"],
        "closings": ["让我们连接吧！", "让我们聊聊！", "期待交流！", "再见！"]
    },
    "arabic": {
        "keywords": ["في", "من", "إلى", "على", "مع", "عن", "أن", "كل", "هذا", "هذه", "التي", "الذي", "لكن", "أو"],
        "greetings": ["مرحبا", "أهلا", "السلام عليكم", "أهلا وسهلا"],
        "connectors": ["أحب", "أهتم بـ", "أعتقد أنه رائع", "أود"],
        "closings": ["لنتواصل!", "لنتحدث!", "مع التحية!", "إلى اللقاء!"]
    },
    "hindi": {
        "keywords": ["का", "के", "की", "में", "से", "को", "पर", "और", "है", "हैं", "था", "थी", "होगा", "होगी"],
        "greetings": ["नमस्ते", "हैलो", "हाय", "आदाब"],
        "connectors": ["मुझे पसंद है", "मैं रुचि रखता हूं", "मुझे लगता है यह बहुत अच्छा है", "मैं चाहूंगा"],
        "closings": ["आइए जुड़ते हैं!", "आइए बात करते हैं!", "धन्यवाद!", "फिर मिलते हैं!"]
    },
    "russian": {
        "keywords": ["в", "на", "с", "по", "для", "от", "до", "из", "к", "у", "о", "при", "за", "под"],
        "greetings": ["Привет", "Здравствуйте", "Хай", "Приветствую"],
        "connectors": ["Мне нравится", "Меня интересует", "Я думаю, это отлично", "Хотелось бы"],
        "closings": ["Давайте подключимся!", "Давайте поговорим!", "До свидания!", "Удачи!"]
    }
}

# Platform-specific cultural adaptations by language
PLATFORM_LANGUAGE_STYLES = {
    "tiktok": {
        "spanish": {"style": "muy casual", "emojis": "🔥✨💫🚀", "tone": "juvenil y divertido"},
        "french": {"style": "décontracté", "emojis": "🔥✨💫🚀", "tone": "jeune et amusant"},
        "german": {"style": "locker", "emojis": "🔥✨💫🚀", "tone": "jung und spaßig"},
        "portuguese": {"style": "bem casual", "emojis": "🔥✨💫🚀", "tone": "jovem e divertido"},
        "japanese": {"style": "カジュアル", "emojis": "🔥✨💫🚀", "tone": "若々しくて楽しい"},
        "korean": {"style": "캐주얼", "emojis": "🔥✨💫🚀", "tone": "젊고 재미있는"},
        "chinese": {"style": "很随意", "emojis": "🔥✨💫🚀", "tone": "年轻有趣"},
        "english": {"style": "ultra-casual", "emojis": "🔥✨💫🚀", "tone": "young and fun"}
    },
    "linkedin": {
        "spanish": {"style": "profesional", "emojis": "", "tone": "respetuoso y profesional"},
        "french": {"style": "professionnel", "emojis": "", "tone": "respectueux et professionnel"},
        "german": {"style": "professionell", "emojis": "", "tone": "respektvoll und professionell"},
        "portuguese": {"style": "profissional", "emojis": "", "tone": "respeitoso e profissional"},
        "japanese": {"style": "プロフェッショナル", "emojis": "", "tone": "敬語で丁寧"},
        "korean": {"style": "전문적", "emojis": "", "tone": "정중하고 전문적"},
        "chinese": {"style": "专业", "emojis": "", "tone": "尊重和专业"},
        "english": {"style": "professional", "emojis": "", "tone": "respectful and professional"}
    }
}

def detect_language_from_bio(bio: str) -> str:
    """Detect language from bio text using keyword matching"""
    if not bio:
        return "english"
    
    bio_lower = bio.lower()
    language_scores = {}
    
    # Score each language based on keyword matches
    for language, data in LANGUAGE_KEYWORDS.items():
        score = 0
        for keyword in data["keywords"]:
            if keyword in bio_lower:
                score += 1
        
        if score > 0:
            language_scores[language] = score
    
    # Return language with highest score, or English as default
    if language_scores:
        detected = max(language_scores, key=language_scores.get)
        print(f"🌍 Detected language: {detected} (score: {language_scores[detected]})")
        return detected
    
    return "english"

def detect_language_from_name(name: str) -> str:
    """Detect language from name patterns (basic heuristics)"""
    if not name:
        return "english"
    
    name_lower = name.lower()
    
    # Simple pattern matching for names
    patterns = {
        "spanish": ["josé", "maría", "carlos", "ana", "luis", "carmen", "antonio", "francisco"],
        "french": ["pierre", "marie", "jean", "claire", "michel", "sophie", "laurent", "isabelle"],
        "german": ["hans", "anna", "klaus", "petra", "wolfgang", "sabine", "michael", "andrea"],
        "portuguese": ["joão", "ana", "carlos", "maria", "pedro", "claudia", "ricardo", "patricia"],
        "italian": ["marco", "giulia", "alessandro", "francesca", "andrea", "elena", "matteo", "chiara"],
        "japanese": ["takeshi", "yuki", "hiroshi", "akiko", "kenji", "mari", "satoshi", "emi"],
        "korean": ["kim", "park", "lee", "jung", "choi", "yoon", "jang", "lim"],
        "chinese": ["wang", "li", "zhang", "liu", "chen", "yang", "huang", "zhao"],
        "arabic": ["ahmed", "fatima", "mohamed", "aisha", "ali", "khadija", "omar", "zainab"],
        "russian": ["ivan", "anna", "dmitri", "elena", "sergei", "maria", "alexander", "olga"]
    }
    
    for language, name_patterns in patterns.items():
        for pattern in name_patterns:
            if pattern in name_lower:
                return language
    
    return "english"

def get_multilingual_prompt_modifier(platform: str, language: str, persona: str) -> str:
    """Get language and platform-specific prompt instructions for OpenAI"""
    
    # Base language instructions
    language_instructions = {
        "spanish": f"Responde en español. Usa un tono {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('spanish', {}).get('tone', 'amigable')}.",
        "french": f"Réponds en français. Utilise un ton {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('french', {}).get('tone', 'amical')}.",
        "german": f"Antworte auf Deutsch. Verwende einen {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('german', {}).get('tone', 'freundlichen')} Ton.",
        "portuguese": f"Responda em português. Use um tom {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('portuguese', {}).get('tone', 'amigável')}.",
        "italian": f"Rispondi in italiano. Usa un tono {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('italian', {}).get('tone', 'amichevole')}.",
        "japanese": f"日本語で返答してください。{PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('japanese', {}).get('tone', '親しみやすい')}トーンを使用してください。",
        "korean": f"한국어로 답변해주세요. {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('korean', {}).get('tone', '친근한')} 톤을 사용해주세요.",
        "chinese": f"请用中文回复。使用{PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('chinese', {}).get('tone', '友好')}的语调。",
        "arabic": f"أجب باللغة العربية. استخدم نبرة {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('arabic', {}).get('tone', 'ودية')}.",
        "hindi": f"हिंदी में जवाब दें। {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('hindi', {}).get('tone', 'मित्रवत')} स्वर का उपयोग करें।",
        "russian": f"Отвечай на русском языке. Используй {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('russian', {}).get('tone', 'дружелюбный')} тон.",
        "english": f"Respond in English. Use a {PLATFORM_LANGUAGE_STYLES.get(platform, {}).get('english', {}).get('tone', 'friendly')} tone."
    }
    
    # Platform-specific cultural notes
    platform_cultural_notes = {
        "tiktok": {
            "spanish": "Usa jerga juvenil y expresiones como 'qué tal', 'genial', 'increíble'.",
            "french": "Utilise l'argot jeune et des expressions comme 'génial', 'incroyable', 'super'.",
            "german": "Verwende Jugendsprache und Ausdrücke wie 'cool', 'mega', 'krass'.",
            "japanese": "若者言葉を使って、「すごい」「やばい」「エモい」などの表現を使用。",
            "korean": "젊은이들의 언어를 사용하고 '대박', '쩐다', '멋져' 같은 표현 사용.",
            "chinese": "使用年轻人的语言，如'太棒了'、'厉害'、'牛'等表达。",
            "english": "Use Gen Z slang and expressions like 'fire', 'slay', 'no cap'."
        },
        "linkedin": {
            "spanish": "Mantén un registro profesional, usa 'usted' si es apropiado.",
            "french": "Maintiens un registre professionnel, utilise 'vous' de manière appropriée.",
            "german": "Halte einen professionellen Ton bei, verwende 'Sie' angemessen.",
            "japanese": "敬語を使用し、ビジネスマナーを守った丁寧な表現。",
            "korean": "존댓말을 사용하고 비즈니스 매너를 지킨 정중한 표현.",
            "chinese": "使用正式商务语言，保持专业和尊重的语调。",
            "english": "Maintain professional language and business etiquette."
        }
    }
    
    base_instruction = language_instructions.get(language, language_instructions["english"])
    cultural_note = platform_cultural_notes.get(platform, {}).get(language, "")
    
    return f"{base_instruction} {cultural_note}".strip()

def get_multilingual_fallback(name: str, platform: str, language: str) -> str:
    """Get platform and language-specific fallback messages"""
    
    first_name = name.split()[0] if name else ""
    lang_data = LANGUAGE_KEYWORDS.get(language, LANGUAGE_KEYWORDS["english"])
    
    greeting = random.choice(lang_data.get("greetings", ["Hi"]))
    connector = random.choice(lang_data.get("connectors", ["I'd love to"]))
    closing = random.choice(lang_data.get("closings", ["Let's connect!"]))
    
    # Platform-specific fallback templates by language
    fallback_templates = {
        "tiktok": {
            "spanish": f"{greeting} {first_name}! {connector} tu contenido. {closing}",
            "french": f"{greeting} {first_name}! {connector} ton contenu. {closing}",
            "german": f"{greeting} {first_name}! {connector} deinen Content. {closing}",
            "portuguese": f"{greeting} {first_name}! {connector} seu conteúdo. {closing}",
            "japanese": f"{greeting}{first_name}さん！あなたのコンテンツが{connector}。{closing}",
            "korean": f"{greeting} {first_name}님! 당신의 콘텐츠를 {connector}. {closing}",
            "chinese": f"{greeting} {first_name}！{connector}你的内容。{closing}",
            "english": f"{greeting} {first_name}! {connector} your content. {closing}"
        },
        "linkedin": {
            "spanish": f"{greeting} {first_name}, {connector} conectar con profesionales como tú. {closing}",
            "french": f"{greeting} {first_name}, {connector} me connecter avec des professionnels comme vous. {closing}",
            "german": f"{greeting} {first_name}, {connector} mich mit Fachleuten wie Ihnen zu vernetzen. {closing}",
            "portuguese": f"{greeting} {first_name}, {connector} conectar com profissionais como você. {closing}",
            "japanese": f"{greeting}{first_name}さん、あなたのような専門家と{connector}。{closing}",
            "korean": f"{greeting} {first_name}님, 당신 같은 전문가와 {connector}. {closing}",
            "chinese": f"{greeting} {first_name}，{connector}与像您这样的专业人士联系。{closing}",
            "english": f"{greeting} {first_name}, {connector} connect with professionals like you. {closing}"
        }
    }
    
    # Get template for platform and language, fallback to English
    template = fallback_templates.get(platform, fallback_templates.get("linkedin", {}))
    return template.get(language, template.get("english", f"Hi {first_name}! Would love to connect!"))

def detect_user_language(name: str, bio: str, platform_hint: str = None) -> str:
    """Comprehensive language detection from name and bio"""
    
    # Try bio detection first (more reliable)
    bio_language = detect_language_from_bio(bio)
    if bio_language != "english":
        return bio_language
    
    # Try name detection
    name_language = detect_language_from_name(name)
    if name_language != "english":
        return name_language
    
    # Platform-based hints (different platforms are popular in different regions)
    platform_language_hints = {
        "weibo": "chinese",
        "vk": "russian",
        "line": "japanese",
        "kakao": "korean"
    }
    
    if platform_hint and platform_hint.lower() in platform_language_hints:
        return platform_language_hints[platform_hint.lower()]
    
    return "english"

def create_multilingual_dm_prompt(name: str, bio: str, platform: str, persona: str, language: str) -> str:
    """Create a comprehensive multilingual prompt for OpenAI"""
    
    first_name = name.split()[0] if name else "there"
    
    # Base prompt in English (for OpenAI understanding)
    base_prompt = f"""Create a personalized direct message for {first_name} based on their bio: "{bio}". 
This is for {platform} platform using the {persona} persona.

Target language: {language}
Platform: {platform}
Persona: {persona}

Requirements:
1. Write the entire message in {language}
2. Keep it natural and culturally appropriate for {language} speakers
3. Adapt to {platform} platform culture and norms
4. Use the {persona} persona approach
5. Keep it concise and engaging
6. Include appropriate cultural greetings and expressions"""
    
    # Add language and platform specific instructions
    multilingual_modifier = get_multilingual_prompt_modifier(platform, language, persona)
    
    return f"{base_prompt}\n\nSpecific instructions: {multilingual_modifier}"

# Enhanced version of your existing generate_dm_with_fallback function
def generate_multilingual_dm(name: str, bio: str, platform: str, language: str = None, persona: str = None) -> dict:
    """
    Generate multilingual DM - enhanced version of your generate_dm_with_fallback
    
    Returns dict with: dm, language, persona, platform, detected_language
    """
    
    # Auto-detect language if not provided
    if language is None:
        language = detect_user_language(name, bio, platform)
    
    # Import your existing functions (avoiding circular imports)
    try:
        from dm_sequences import match_persona, PERSONAS, initialize_openai_client, generate_dm_with_openai_v1, generate_dm_with_openai_v0
        from personas import PERSONAS as PERSONAS_DATA
    except ImportError:
        # Fallback if imports fail
        print("⚠️ Could not import dm_sequences. Using basic fallback.")
        return {
            "dm": get_multilingual_fallback(name, platform, language),
            "language": language,
            "persona": "fallback",
            "platform": platform,
            "detected_language": language,
            "method": "fallback"
        }
    
    # Get persona (your existing logic)
    if persona is None:
        persona = match_persona(bio)
    
    print(f"🌍 Generating {language} DM for {platform} using {persona} persona")
    
    # Create multilingual prompt
    multilingual_prompt = create_multilingual_dm_prompt(name, bio, platform, persona, language)
    
    # Try OpenAI API (your existing logic)
    client, version = initialize_openai_client()
    
    if client is None:
        print("⚠️ OpenAI not available, using multilingual fallback")
        return {
            "dm": get_multilingual_fallback(name, platform, language),
            "language": language,
            "persona": persona,
            "platform": platform,
            "detected_language": language,
            "method": "fallback"
        }
    
    try:
        messages = [
            {"role": "system", "content": f"You're a multilingual social media outreach assistant. You can write natural, culturally appropriate DMs in {language} for {platform}."},
            {"role": "user", "content": multilingual_prompt}
        ]
        
        if version == "v1":
            dm_text = generate_dm_with_openai_v1(client, messages)
        elif version == "v0":
            dm_text = generate_dm_with_openai_v0(client, messages)
        else:
            raise Exception("Unknown OpenAI version")
        
        return {
            "dm": dm_text.strip(),
            "language": language,
            "persona": persona,
            "platform": platform,
            "detected_language": language,
            "method": "openai"
        }
            
    except Exception as e:
        print(f"⚠️ OpenAI error: {e}")
        print(f"   Using multilingual fallback for {language}")
        return {
            "dm": get_multilingual_fallback(name, platform, language),
            "language": language,
            "persona": persona,
            "platform": platform,
            "detected_language": language,
            "method": "fallback",
            "error": str(e)
        }

def generate_multilingual_batch(contacts: List[Dict], platform: str = "twitter", target_language: str = None) -> List[Dict]:
    """
    Generate multilingual DMs for multiple contacts
    
    Args:
        contacts: List of dicts with 'name' and 'bio' keys
        platform: Target platform
        target_language: Force specific language (None for auto-detection)
    """
    
    results = []
    
    print(f"🌍 Generating multilingual DMs for {platform}...")
    
    for contact in contacts:
        try:
            result = generate_multilingual_dm(
                name=contact.get("name", ""),
                bio=contact.get("bio", ""),
                platform=platform,
                language=target_language
            )
            
            # Add original contact info
            result.update({
                "original_name": contact.get("name"),
                "original_bio": contact.get("bio"),
                "length": len(result["dm"])
            })
            
            results.append(result)
            
        except Exception as e:
            print(f"⚠️ Error generating multilingual DM for {contact.get('name')}: {e}")
            results.append({
                "original_name": contact.get("name"),
                "original_bio": contact.get("bio"),
                "dm": get_multilingual_fallback(contact.get("name", ""), platform, target_language or "english"),
                "language": target_language or "english",
                "persona": "error",
                "platform": platform,
                "detected_language": "unknown",
                "method": "error_fallback",
                "error": str(e),
                "length": 0
            })
    
    return results

def test_multilingual_generation():
    """Test multilingual DM generation"""
    
    print("🌍 Testing Multilingual DM Generation")
    print("=" * 50)
    
    # Test contacts with different languages
    test_contacts = [
        {"name": "José García", "bio": "Entrenador de fitness que ayuda a personas a alcanzar sus metas de salud"},
        {"name": "Marie Dubois", "bio": "Créatrice de contenu beauté sur YouTube avec des tutoriels maquillage"},
        {"name": "Hans Mueller", "bio": "Software-Entwickler mit Leidenschaft für künstliche Intelligenz"},
        {"name": "João Silva", "bio": "Criador de conteúdo tech no TikTok, cobrindo gadgets e inovações"},
        {"name": "Marco Rossi", "bio": "Imprenditore digitale e consulente marketing per startup"},
        {"name": "田中太郎", "bio": "ゲーム実況者でTwitchでストリーミング配信をしています"},
        {"name": "김민수", "bio": "유튜브에서 요리 콘텐츠를 만드는 크리에이터입니다"},
        {"name": "王小明", "bio": "科技博主，专注人工智能和机器学习内容创作"},
        {"name": "Ahmed Hassan", "bio": "مطور تطبيقات ومهتم بالتكنولوجيا الحديثة"},
        {"name": "Ravi Kumar", "bio": "फिटनेस ट्रेनर और स्वास्थ्य सलाहकार"},
        {"name": "Ivan Petrov", "bio": "Создатель контента о криптовалютах и блокчейн технологиях"}
    ]
    
    platforms = ["twitter", "tiktok", "linkedin"]
    
    for platform in platforms:
        print(f"\n📱 Testing {platform.upper()}:")
        print("-" * 40)
        
        # Test first 3 contacts for each platform
        results = generate_multilingual_batch(test_contacts[:3], platform)
        
        for result in results:
            print(f"👤 {result['original_name']} ({result['detected_language']}):")
            print(f"💬 {result['dm']}")
            print(f"🎭 Persona: {result['persona']} | Method: {result['method']}")
            print()

if __name__ == "__main__":
    test_multilingual_generation()