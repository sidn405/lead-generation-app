
from datetime import datetime
import time
from playwright.sync_api import sync_playwright
import pandas as pd
import json
import csv
import re
import random
from dm_sequences import generate_dm_with_fallback
import os
from persistence import save_leads_to_files

# Directory where your CSV files are saved
CSV_DIR = os.path.join(os.getcwd(), "csv_exports")
os.makedirs(CSV_DIR, exist_ok=True)
# Import the centralized usage tracker
from usage_tracker import setup_scraper_with_limits, finalize_scraper_results

# 🚀 NEW: Import the enhanced config system
from config_loader import ConfigLoader, should_exclude_account, get_platform_config

# 🚀 Import smart duplicate detection
try:
    from smart_duplicate_handler import process_leads_with_smart_deduplication
    from deduplication_config import DeduplicationMode, apply_deduplication_strategy
    SMART_DEDUP_AVAILABLE = True
except ImportError:
    print("⚠️ Smart deduplication not available - using basic dedup")
    SMART_DEDUP_AVAILABLE = False

PLATFORM_NAME = "medium"

# Load Medium session state
try:
    with open("medium_auth.json", "r") as f:
        storage_state = json.load(f)
except FileNotFoundError:
    print("⚠️ medium_auth.json not found - continuing without authentication")
    storage_state = None

# ✅ CORRECT: Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = config_loader.get_platform_config('medium')

# 🎯 UNIVERSAL NICHE CONFIGURATION
NICHE = config.get("niche", "fitness")  # Default to fitness if not configured

# 🎯 UNIVERSAL END CUSTOMER SEARCH TERMS BY NICHE (Medium-specific)
NICHE_CUSTOMER_MEDIUM_SEARCHES = {
    'fitness': [
        # Transformation/Journey Stories (Premium Leads - $80-250 each)
        "my weight loss journey",
        "fitness transformation story", 
        "how I lost 25 pounds",
        "from obese to fit",
        
        # Beginner/Help-Seeking (High Converting - $60-150 each)
        "beginner fitness routine",
        "how to start working out",
        "fitness for beginners",
        "best exercises for beginners",
        
        # Problem/Struggle Content (High Intent - $70-200 each)
        "can't lose weight",
        "struggling with motivation",
        "why am I not losing weight",
        "fitness plateau breakthrough",
        
        # Product/Service Reviews (Buying Intent - $50-120 each)
        "best fitness apps",
        "personal trainer worth it",
        "home gym equipment review",
        
        # Lifestyle/Balance (Standard Leads - $40-100 each)
        "busy mom workout routine",
        "fitness during pregnancy",
        "working out with kids",
        "exercise for seniors",
        
        # Goal-Oriented (Standard Leads - $30-80 each)
        "summer body preparation",
        "new year fitness goals",
        "wedding fitness plan",
        "get in shape fast"
    ],
    'health': [
        "natural anxiety relief journey",
        "healing chronic pain naturally",
        "my autoimmune recovery story",
        "overcoming depression without medication",
        "gut health transformation",
        "thyroid healing journey",
        "chronic fatigue recovery",
        "natural remedies that work",
        "holistic health approach",
        "functional medicine experience"
    ],
    'business': [
        "my entrepreneurship journey",
        "failed startup lessons learned",
        "bootstrapping a business",
        "side hustle success story",
        "quitting my corporate job",
        "first time entrepreneur mistakes",
        "small business survival guide",
        "passive income reality check",
        "freelancing challenges",
        "business credit for beginners"
    ],
    'tech': [
        "career change to tech at 30",
        "self taught programmer journey",
        "coding bootcamp experience",
        "first tech job search",
        "imposter syndrome in tech",
        "learning to code as a beginner",
        "tech industry for women",
        "programming language choice",
        "web development career path",
        "remote work in tech"
    ],
    'beauty': [
        "skincare routine transformation",
        "natural beauty journey",
        "acne recovery story",
        "anti aging skincare guide",
        "budget beauty routine",
        "sensitive skin solutions",
        "makeup for beginners",
        "hair loss recovery",
        "natural skincare ingredients",
        "beauty industry reality"
    ],
    'finance': [
        "paying off debt journey",
        "financial independence story",
        "budgeting for beginners",
        "investing mistakes to avoid",
        "emergency fund success",
        "retirement planning basics",
        "money mindset transformation",
        "frugal living tips",
        "side income ideas",
        "credit score improvement"
    ],
    'real_estate': [
        "first time home buyer experience",
        "real estate investing journey",
        "house flipping reality",
        "rental property lessons",
        "real estate market analysis",
        "property management challenges",
        "wholesale real estate guide",
        "real estate agent struggles",
        "foreclosure investing tips",
        "BRRRR method experience"
    ],
    'relationships': [
        "marriage counseling journey",
        "dating after divorce",
        "toxic relationship recovery",
        "attachment styles explained",
        "communication in relationships",
        "self love journey",
        "dating anxiety solutions",
        "long distance relationship",
        "relationship boundaries guide",
        "healing from breakup"
    ]
}

# 🎯 GET SEARCH TERM FROM CONFIG
def get_search_term_from_config():
    """
    Get search term from config, with fallback to hardcoded terms
    
    Config options:
    - "search_term": "single search term"                    # Use this exact term
    - "search_term": ["term1", "term2", "term3"]            # Pick randomly from list  
    - "search_term": null (or omitted)                      # Use hardcoded fallback terms
    """
    
    # Try to get search term from config first
    config_search_term = config.get("search_term", None)
    
    if config_search_term:
        # If config has multiple search terms (list), pick one randomly
        if isinstance(config_search_term, list):
            selected_term = random.choice(config_search_term)
            print(f"🎯 Using config search term (from list): '{selected_term}'")
            return selected_term
        else:
            # Single search term from config
            print(f"🎯 Using config search term: '{config_search_term}'")
            return config_search_term
    else:
        # Fallback to hardcoded terms if not in config
        fallback_term = random.choice(NICHE_CUSTOMER_MEDIUM_SEARCHES.get(NICHE, NICHE_CUSTOMER_MEDIUM_SEARCHES['fitness']))
        print(f"🎯 No search term in config - using fallback: '{fallback_term}'")
        return fallback_term

CURRENT_SEARCH = get_search_term_from_config()

# Extract config values
MAX_SCROLLS = config["max_scrolls"]
DELAY_BETWEEN_SCROLLS = config.get("delay_between_scrolls", 4)
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 45000)
MAX_PAGES = config.get("max_pages", 3)

# Medium End Customer specific config
MAX_ARTICLES_TO_CHECK = 50     # Number of articles to analyze
MAX_AUTHORS_PER_ARTICLE = 10   # Max authors to extract per article batch

# 🚀 Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")
SAVE_RAW_LEADS = config.get("save_raw_leads", True)

# 🚀 NEW: Show excluded accounts info
excluded_accounts = config_loader.get_excluded_accounts('medium')
print(f"📋 Medium {NICHE.title()} End Customer Config Loaded:")
print(f"  🎯 Search Term: '{CURRENT_SEARCH}' {'(from config)' if config.get('search_term') else '(fallback)'}")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  📰 Max Articles: {MAX_ARTICLES_TO_CHECK}")
print(f"  ⏱️ Delay: {DELAY_BETWEEN_SCROLLS}s")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
print(f"  🎯 Niche: {NICHE}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")

def is_niche_end_customer_medium(name, bio, article_titles="", reading_patterns="", niche=None):
    """
    🎯 Universal function to determine if Medium user is END CUSTOMER vs professional
    
    Medium context: Focus on article consumption, engagement patterns, bio content
    """
    if niche is None:
        niche = NICHE
        
    analysis_text = f"{name} {bio} {article_titles} {reading_patterns}".lower()
    
    # 🚫 EXCLUDE PROFESSIONALS (More permissive - only clear business language)
    professional_indicators = [
        # Only exclude clear business/service language
        'coaching services', 'personal training', 'nutrition plans',
        'transformation programs', 'coaching programs', 'wellness programs',
        'book a consultation', 'dm for coaching', 'custom plans',
        'coaching business', 'my course', 'my program', 'my method',
        'contact me for', 'services available', 'consultation available',
        'hire me', 'work with me', 'dm for services'
    ]
    
    for indicator in professional_indicators:
        if indicator in analysis_text:
            return False, 0, "professional"
    
    # 🎯 UNIVERSAL END CUSTOMER SIGNALS
    end_customer_signals = {
        # Premium Leads ($80-250 each) - High intent/transformation
        'transformation_sharing': [
            'my journey', 'my transformation', 'my story', 'my experience',
            'lost weight', 'gained muscle', 'changed my life', 'transformation',
            'before and after', 'progress update', 'documenting my',
            'sharing my experience', 'this is my story', 'my recovery',
            'my healing', 'my success', 'my failure', 'learned from'
        ],
        
        # Premium Leads - Problem/struggle documentation
        'struggle_documentation': [
            'struggling with', 'can\'t lose weight', 'plateau', 'stuck',
            'not seeing results', 'frustrated with', 'tired of',
            'nothing works', 'tried everything', 'desperate for help',
            'at my wit\'s end', 'need help', 'seeking advice',
            'overwhelmed', 'confused', 'lost', 'failed'
        ],
        
        # Premium Leads - Medical/urgent motivation
        'health_motivated': [
            'doctor told me', 'health scare', 'medical advice', 'diagnosis',
            'prescribed', 'treatment', 'therapy', 'recovery',
            'medical condition', 'health concerns', 'doctor recommended',
            'urgent', 'emergency', 'crisis', 'breaking point'
        ],
        
        # Standard Leads ($40-100 each) - Goal-oriented content
        'goal_oriented': [
            'my goal is', 'trying to', 'want to', 'working towards',
            'new year resolution', 'target', 'objective', 'plan to',
            'hoping to', 'aiming for', 'striving to', 'dream of',
            'aspire to', 'desire to', 'wish to'
        ],
        
        # Standard Leads - Beginner seeking guidance
        'beginner_guidance': [
            'new to', 'beginner', 'just started', 'where to start',
            'complete beginner', 'never done', 'first time',
            'don\'t know how', 'need guidance', 'learning about',
            'trying to understand', 'researching', 'exploring'
        ],
        
        # Volume Leads ($30-80 each) - Product/service research
        'product_research': [
            'best apps', 'equipment review', 'worth the money',
            'should i buy', 'recommendations', 'anyone tried',
            'thinking of getting', 'looking for', 'shopping for',
            'comparing', 'reviews', 'experiences with',
            'worth it', 'good investment', 'value for money'
        ],
        
        # Volume Leads - Lifestyle integration
        'lifestyle_focus': [
            'busy mom', 'working parent', 'busy professional', 'no time',
            'work life balance', 'fitting in', 'quick solutions',
            'efficient', 'time-saving', 'busy schedule',
            'juggling', 'multitasking', 'overwhelmed'
        ]
    }
    
    # Score customer signals with Medium-specific weighting
    total_score = 0
    customer_type = "volume"
    matched_categories = []
    
    for signal_type, signals in end_customer_signals.items():
        category_score = 0
        for signal in signals:
            if signal in analysis_text:
                category_score += 1
        
        if category_score > 0:
            matched_categories.append(signal_type)
            
            if signal_type in ['transformation_sharing', 'struggle_documentation', 'health_motivated']:
                total_score += category_score * 4  # High value signals
                customer_type = "premium"
            elif signal_type in ['goal_oriented', 'beginner_guidance']:
                total_score += category_score * 2
                if customer_type != "premium":
                    customer_type = "standard"
            else:  # product_research, lifestyle_focus
                total_score += category_score
    
    is_customer = total_score >= 0.3  # Lower threshold for Medium (was 0.5)
    # Debug output
    if total_score > 0:
        print(f"    🔍 Analysis: '{analysis_text[:50]}...' | Score: {total_score} | Categories: {matched_categories}")
    
    return is_customer, total_score, customer_type

def extract_medium_customer_intelligence(name, bio, article_titles="", engagement_data="", niche=None):
    """
    🧠 Extract universal customer intelligence from user data
    """
    if niche is None:
        niche = NICHE
        
    combined_text = f"{name} {bio} {article_titles} {engagement_data}".lower()
    
    intelligence = {
        'content_focus': 'general',
        'transformation_stage': 'unknown',
        'goals': [],
        'pain_points': [],
        'reading_patterns': [],
        'urgency_level': 'low',
        'content_engagement': 'passive'
    }
    
    # Determine content focus from article titles and bio (niche-specific)
    niche_content_focuses = {
        'fitness': {
            'weight_loss': ['weight loss', 'lose weight', 'fat loss', 'slim down'],
            'muscle_building': ['muscle', 'strength', 'build', 'bulk', 'gains'],
            'general_fitness': ['fitness', 'workout', 'exercise', 'training'],
            'wellness': ['wellness', 'health', 'lifestyle', 'balance'],
            'nutrition': ['nutrition', 'diet', 'eating', 'food', 'meal']
        },
        'health': {
            'mental_health': ['anxiety', 'depression', 'stress', 'mental health'],
            'chronic_conditions': ['chronic', 'autoimmune', 'thyroid', 'diabetes'],
            'natural_healing': ['natural', 'holistic', 'alternative', 'herbs'],
            'pain_management': ['pain', 'inflammation', 'recovery', 'healing'],
            'gut_health': ['gut', 'digestive', 'microbiome', 'probiotics']
        },
        'business': {
            'entrepreneurship': ['startup', 'entrepreneur', 'business', 'company'],
            'freelancing': ['freelance', 'gig', 'contract', 'independent'],
            'side_hustle': ['side hustle', 'extra income', 'passive income'],
            'career_change': ['career change', 'pivot', 'transition', 'switch'],
            'marketing': ['marketing', 'sales', 'branding', 'promotion']
        },
        'tech': {
            'programming': ['coding', 'programming', 'development', 'software'],
            'career_change': ['career change', 'transition', 'bootcamp', 'switch'],
            'web_development': ['web', 'frontend', 'backend', 'fullstack'],
            'data_science': ['data', 'analytics', 'machine learning', 'ai'],
            'product_management': ['product', 'pm', 'management', 'strategy']
        },
        'beauty': {
            'skincare': ['skincare', 'skin', 'acne', 'anti aging'],
            'makeup': ['makeup', 'cosmetics', 'beauty', 'foundation'],
            'hair_care': ['hair', 'hair loss', 'hair growth', 'styling'],
            'natural_beauty': ['natural', 'organic', 'clean beauty', 'diy'],
            'anti_aging': ['anti aging', 'wrinkles', 'youth', 'aging']
        },
        'finance': {
            'debt_management': ['debt', 'pay off', 'credit', 'bankruptcy'],
            'investing': ['invest', 'stocks', 'portfolio', 'retirement'],
            'budgeting': ['budget', 'save', 'frugal', 'money management'],
            'financial_independence': ['fire', 'financial freedom', 'retire early'],
            'real_estate': ['real estate', 'property', 'mortgage', 'rent']
        }
    }
    
    content_focuses = niche_content_focuses.get(niche, niche_content_focuses['fitness'])
    focus_scores = {}
    for focus_type, keywords in content_focuses.items():
        score = sum(1 for keyword in keywords if keyword in combined_text)
        if score > 0:
            focus_scores[focus_type] = score
    
    if focus_scores:
        intelligence['content_focus'] = max(focus_scores, key=focus_scores.get)
    
    # Determine transformation stage
    stage_indicators = {
        'just_starting': ['new to', 'beginner', 'just started', 'where to start'],
        'early_progress': ['first week', 'first month', 'starting to see'],
        'mid_journey': ['making progress', 'continuing', 'still working'],
        'struggling': ['plateau', 'stuck', 'not working', 'frustrated'],
        'success_sharing': ['achieved', 'reached my goal', 'success story']
    }
    
    for stage, indicators in stage_indicators.items():
        if any(indicator in combined_text for indicator in indicators):
            intelligence['transformation_stage'] = stage
            break
    
    # Extract goals (niche-specific)
    niche_goals = {
        'fitness': ['lose weight', 'build muscle', 'get stronger', 'run marathon', 'abs', 'toned'],
        'health': ['heal naturally', 'reduce anxiety', 'manage pain', 'improve energy', 'sleep better'],
        'business': ['start business', 'make money', 'quit job', 'financial freedom', 'passive income'],
        'tech': ['learn coding', 'career change', 'build app', 'get job', 'freelance'],
        'beauty': ['clear skin', 'anti aging', 'look younger', 'hair growth', 'natural beauty'],
        'finance': ['pay off debt', 'save money', 'invest', 'budget better', 'financial security']
    }
    
    for goal in niche_goals.get(niche, []):
        if goal in combined_text:
            intelligence['goals'].append(goal)
    
    # Extract pain points (universal)
    pain_indicators = [
        'no time', 'busy schedule', 'no motivation', 'plateau',
        'not seeing results', 'frustrated', 'confused', 'overwhelmed',
        'expensive', 'don\'t know how', 'afraid to start', 'self conscious',
        'stressed', 'anxious', 'depressed', 'tired'
    ]
    
    for pain in pain_indicators:
        if pain in combined_text:
            intelligence['pain_points'].append(pain)
    
    # Determine reading patterns
    reading_indicators = {
        'how_to_seeker': ['how to', 'guide', 'step by step', 'tutorial'],
        'story_consumer': ['story', 'journey', 'experience', 'transformation'],
        'research_oriented': ['review', 'comparison', 'best', 'vs', 'analyze'],
        'problem_solver': ['help', 'solution', 'fix', 'overcome', 'deal with']
    }
    
    for pattern_type, indicators in reading_indicators.items():
        if any(indicator in combined_text for indicator in indicators):
            intelligence['reading_patterns'].append(pattern_type)
    
    # Determine urgency level
    urgent_indicators = [
        'urgent', 'immediate', 'asap', 'quickly', 'fast results',
        'wedding', 'vacation', 'reunion', 'event', 'deadline'
    ]
    
    if any(indicator in combined_text for indicator in urgent_indicators):
        intelligence['urgency_level'] = 'high'
    elif intelligence['transformation_stage'] in ['struggling', 'just_starting']:
        intelligence['urgency_level'] = 'medium'
    
    # Determine engagement level
    if any(engage in combined_text for engage in ['comment', 'respond', 'question', 'help']):
        intelligence['content_engagement'] = 'active'
    elif any(consume in combined_text for consume in ['read', 'follow', 'subscribe']):
        intelligence['content_engagement'] = 'moderate'
    
    return intelligence

def extract_end_customers_from_search_results(page):
    """Extract end customer data directly from search results without navigating to articles"""
    print(f"📰 Analyzing search results for {NICHE} end customers...")
    
    customers_data = []
    
    try:
        # Stay on search results page - don't navigate away
        print("  📍 Staying on search results page to extract data...")
        
        # Extract information directly from search results page
        
        # Find article cards/elements in search results
        article_selectors = [
            'article',
            '[data-testid="story"]',
            '.story',
            '.medium-story',
            '[class*="story"]'
        ]
        
        article_elements = []
        for selector in article_selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    article_elements = elements
                    print(f"  ✅ Found {len(elements)} article elements using: {selector}")
                    break
            except:
                continue
        
        if not article_elements:
            print("  ⚠️ No article elements found in search results")
            return customers_data
        
        # Process each article element in search results
        for i, article_element in enumerate(article_elements[:MAX_ARTICLES_TO_CHECK]):
            try:
                # Extract article title
                article_title = ""
                title_selectors = ['h2', 'h3', '[data-testid="storyTitle"]', '.title', 'a[data-testid="story-title"]']
                
                for title_selector in title_selectors:
                    try:
                        title_el = article_element.query_selector(title_selector)
                        if title_el:
                            article_title = title_el.inner_text().strip()
                            if article_title and len(article_title) > 5:
                                break
                    except:
                        continue
                
                # Extract article preview/snippet with better debugging
                article_preview = ""
                preview_selectors = ['p', '.story-excerpt', '[data-testid="storyPreview"]', '.description', '.subtitle']
                
                for preview_selector in preview_selectors:
                    try:
                        preview_elements = article_element.query_selector_all(preview_selector)
                        for preview_el in preview_elements[:3]:  # Check first 3 elements
                            preview_text = preview_el.inner_text().strip()
                            if (preview_text and len(preview_text) > 20 and len(preview_text) < 500 and
                                preview_text != article_title and
                                not preview_text.startswith('Follow') and
                                not preview_text.startswith('Subscribe')):
                                article_preview = preview_text
                                break
                        if article_preview:
                            break
                    except:
                        continue
                
                print(f"      📄 Preview found: {len(article_preview)} chars")
                if article_preview:
                    print(f"      📄 Preview: {article_preview[:80]}...")
                
                # Extract author information from article card
                author_name = ""
                author_url = ""
                
                author_selectors = [
                    'a[href*="/@"]',
                    '[data-testid="authorName"]',
                    '.author-name',
                    '[class*="author"] a'
                ]
                
                for author_selector in author_selectors:
                    try:
                        author_el = article_element.query_selector(author_selector)
                        if author_el:
                            author_name = author_el.inner_text().strip()
                            author_href = author_el.get_attribute('href')
                            if author_href and '/@' in author_href:
                                if author_href.startswith('/'):
                                    author_url = 'https://medium.com' + author_href
                                else:
                                    author_url = author_href
                                break
                    except:
                        continue
                
                # Skip if no key information found (more permissive)
                if not article_title and not article_preview:
                    print(f"      ❌ No content found for article {i+1}")
                    continue
                    
                # More permissive - allow articles without author if we have content
                if not author_name:
                    author_name = f"Author_{i+1}"  # Generate placeholder name
                    print(f"      ⚠️ No author found, using placeholder: {author_name}")
                
                # Use title as fallback if no preview
                if not article_preview and article_title:
                    article_preview = article_title
                    print(f"      💡 Using title as preview: {article_preview[:40]}...")
                
                print(f"    📖 {i+1}. {article_title[:40]}... by {author_name}")
                print(f"      📄 Preview: {article_preview[:60]}..." if article_preview else "      📄 Using title as content")
                
                # Combine text for analysis - ensure we have content to analyze
                combined_text = f"{article_title} {article_preview}".lower()
                print(f"      🔍 Combined text: {combined_text[:100]}...")
                
                # Look for NICHE INTEREST indicators (more inclusive)
                niche_interest_indicators = {
                    'fitness': [
                        # Core fitness terms
                        'exercise', 'workout', 'fitness', 'training', 'gym', 'health',
                        'weight', 'diet', 'nutrition', 'muscle', 'strength', 'cardio',
                        'running', 'walking', 'yoga', 'pilates', 'swimming', 'cycling',
                        
                        # Personal journey terms  
                        'journey', 'transformation', 'progress', 'goal', 'challenge',
                        'struggle', 'success', 'failure', 'motivation', 'inspiration',
                        'change', 'improvement', 'habit', 'routine', 'lifestyle',
                        
                        # Problem/solution terms
                        'lose', 'gain', 'build', 'improve', 'reduce', 'increase',
                        'plateau', 'stuck', 'help', 'advice', 'tips', 'guide',
                        'beginner', 'started', 'trying', 'learning', 'discovering',
                        
                        # Body/health terms
                        'body', 'fat', 'pounds', 'shape', 'fit', 'healthy', 'energy',
                        'pain', 'injury', 'recovery', 'wellness', 'balance'
                    ],
                    'health': [
                        'health', 'healing', 'wellness', 'natural', 'anxiety', 'stress',
                        'depression', 'chronic', 'pain', 'recovery', 'therapy', 'treatment',
                        'mental', 'emotional', 'physical', 'spiritual', 'holistic',
                        'journey', 'transformation', 'struggle', 'overcome', 'healing',
                        'autoimmune', 'gut', 'supplements', 'vitamins', 'herbs', 'nutrition',
                        'sleep', 'energy', 'fatigue', 'inflammation', 'digestion'
                    ],
                    'business': [
                        'business', 'entrepreneur', 'startup', 'freelance', 'work',
                        'money', 'income', 'career', 'job', 'success', 'failure',
                        'journey', 'lessons', 'experience', 'struggle', 'challenge',
                        'growth', 'scale', 'profit', 'revenue', 'marketing', 'sales',
                        'quit', 'corporate', 'freedom', 'independence', 'risk', 'investment'
                    ],
                    'tech': [
                        'coding', 'programming', 'tech', 'software', 'development', 'code',
                        'career', 'job', 'bootcamp', 'developer', 'engineer', 'computer',
                        'learning', 'beginner', 'self taught', 'tutorial', 'course',
                        'javascript', 'python', 'react', 'web', 'app', 'website',
                        'change', 'transition', 'switch', 'new', 'first', 'journey'
                    ],
                    'beauty': [
                        'beauty', 'skincare', 'skin', 'makeup', 'hair', 'face',
                        'acne', 'aging', 'wrinkles', 'routine', 'products', 'tips',
                        'natural', 'organic', 'diy', 'homemade', 'ingredients',
                        'transformation', 'journey', 'struggle', 'confidence', 'self',
                        'appearance', 'look', 'feel', 'beautiful', 'glow', 'healthy'
                    ],
                    'finance': [
                        'money', 'debt', 'budget', 'invest', 'financial', 'finance',
                        'save', 'savings', 'retirement', 'emergency', 'credit', 'income',
                        'freedom', 'independence', 'wealthy', 'rich', 'poor', 'broke',
                        'struggle', 'journey', 'success', 'failure', 'lesson', 'tips',
                        'frugal', 'cheap', 'expensive', 'cost', 'price', 'value'
                    ]
                }
                
                current_indicators = niche_interest_indicators.get(NICHE, niche_interest_indicators['fitness'])
                
                # More flexible matching - check if any niche indicator appears in text
                matched_indicators = [indicator for indicator in current_indicators if indicator in combined_text]
                has_niche_content = len(matched_indicators) > 0
                
                print(f"      🎯 Matched {NICHE} indicators: {matched_indicators[:5]}{'...' if len(matched_indicators) > 5 else ''}")
                print(f"      🎯 {NICHE.title()} content detected: {has_niche_content}")
                
                if has_niche_content:
                    print(f"      🔍 Processing as {NICHE}-interested author...")
                    
                    # Create a simple scoring system based on content relevance
                    score = len(matched_indicators)
                    
                    # Determine customer type based on content and indicators (more inclusive)
                    premium_indicators = ['journey', 'transformation', 'struggle', 'failed', 'recovery', 'my', 'personal', 'experience']
                    standard_indicators = ['beginner', 'learning', 'new to', 'guide', 'tips', 'help', 'advice', 'started', 'trying']
                    
                    if any(premium in matched_indicators + [article_title.lower(), article_preview.lower()] for premium in premium_indicators):
                        customer_type = "premium"
                    elif any(standard in matched_indicators + [article_title.lower(), article_preview.lower()] for standard in standard_indicators):
                        customer_type = "standard" 
                    else:
                        customer_type = "volume"  # Default to volume instead of excluding
                    
                    print(f"      📊 {NICHE.title()} interest result: Score: {score} | Type: {customer_type}")
                    
                    # Very inclusive - include anyone with any niche content (lowered from 1 to 0.5)
                    if score >= 0.5:
                        customers_data.append({
                            'name': author_name,
                            'bio': article_preview[:150] + "..." if len(article_preview) > 150 else article_preview or f"Medium author interested in: {article_title[:50]}...",
                            'profile_url': author_url,
                            'article_title': article_title,
                            'article_url': f"https://medium.com/story/{article_title.replace(' ', '-').lower()}",
                            'customer_type': customer_type,
                            'score': score,
                            'source': 'search_results'
                        })
                        
                        print(f"      ✅ {NICHE.title()}-interested person found: {author_name} | {customer_type} | Score: {score}")
                    else:
                        print(f"      ❌ Not enough {NICHE} indicators: Score {score} < 0.5")
                else:
                    print(f"      ❌ No {NICHE} content indicators found in text")
                
            except Exception as e:
                print(f"    ⚠️ Error processing article element {i+1}: {e}")
                continue
        
    except Exception as e:
        print(f"    ⚠️ Error analyzing article: {e}")
    
    return customers_data

def extract_medium_niche_customers(page):
    """Extract END CUSTOMERS from Medium search results without navigating away - Universal version"""
    print(f"🎯 Extracting {NICHE} end customers from Medium search results...")
    
    all_leads = []
    excluded_count = 0
    
    # Extract end customers directly from search results page
    print(f"📰 Analyzing search results page for {NICHE} end customer content...")
    
    # Extract customers from search results
    customers_data = extract_end_customers_from_search_results(page)
    
    if not customers_data:
        print(f"❌ No {NICHE} end customers found in search results")
        return []
        
    
    print(f"📊 Processing {len(customers_data)} potential {NICHE} end customers...")
    
    for customer_data in customers_data:
        try:
            name = customer_data['name']
            bio = customer_data['bio']
            profile_url = customer_data['profile_url']
            article_title = customer_data['article_title']
            customer_type = customer_data['customer_type']
            score = customer_data['score']
            source = customer_data['source']
            
            # Check for exclusion
            if should_exclude_account(name, PLATFORM_NAME, config_loader):
                excluded_count += 1
                continue
            
            # Extract customer intelligence
            intelligence = extract_medium_customer_intelligence(
                name, bio, article_title, customer_data.get('comment_preview', ''), NICHE
            )
            
            # Create display handle
            handle = f"@{name.replace(' ', '').lower()}"
            
            # Create bio from intelligence
            bio_parts = []
            if intelligence['content_focus'] != 'general':
                bio_parts.append(f"Interested in {intelligence['content_focus']}")
            if intelligence['goals']:
                bio_parts.append(f"Goals: {', '.join(intelligence['goals'])}")
            if intelligence['transformation_stage'] != 'unknown':
                bio_parts.append(f"Stage: {intelligence['transformation_stage']}")
            
            enhanced_bio = f"Medium reader/writer - {', '.join(bio_parts)}" if bio_parts else bio
            
            # Create niche end customer lead
            lead = {
                "name": name,
                "handle": handle,
                "bio": enhanced_bio[:200] + "..." if len(enhanced_bio) > 200 else enhanced_bio,
                "url": profile_url or f"https://medium.com/search?q={name}",
                "platform": "medium",
                
                # 🎯 UNIVERSAL CUSTOMER CLASSIFICATION
                "customer_type": f"{NICHE}_end_customer",
                "lead_quality": customer_type,
                "search_source": CURRENT_SEARCH,
                
                # 🧠 UNIVERSAL INTELLIGENCE
                "content_focus": intelligence['content_focus'],
                "transformation_stage": intelligence['transformation_stage'],
                "niche_goals": ", ".join(intelligence['goals']) if intelligence['goals'] else f"General {NICHE}",
                "pain_points": ", ".join(intelligence['pain_points']) if intelligence['pain_points'] else "None identified",
                "reading_patterns": ", ".join(intelligence['reading_patterns']) if intelligence['reading_patterns'] else "General reading",
                "urgency_level": intelligence['urgency_level'],
                "content_engagement": intelligence['content_engagement'],
                
                # Context fields
                "source_type": source,
                "article_context": article_title[:100] + "..." if len(article_title) > 100 else article_title,
                "comment_preview": customer_data.get('comment_preview', 'N/A'),
                
                # Standard fields
                'followers': 'Not available on Medium',
                'location': 'Not specified',
                'search_term': CURRENT_SEARCH,
                'extraction_method': 'Search Results Analysis',
                'relevance_score': score,
                'source_article_url': customer_data.get('article_url', 'N/A')
            }
            
            all_leads.append(lead)
            print(f"✅ {name[:20]}... | {customer_type} | {intelligence['content_focus']} | Score: {score}")
            
        except Exception as e:
            print(f"⚠️ Error processing customer: {e}")
            continue
    
    # Remove duplicates and provide analytics
    if all_leads:
        unique_results = []
        seen_names = set()
        for result in all_leads:
            name_key = result['name'].lower().strip()
            if name_key not in seen_names:
                unique_results.append(result)
                seen_names.add(name_key)
        
        # Quality and engagement breakdown
        quality_counts = {}
        focus_counts = {}
        for result in unique_results:
            quality = result['lead_quality']
            focus = result['content_focus']
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
            focus_counts[focus] = focus_counts.get(focus, 0) + 1
        
        print(f"\n📊 MEDIUM {NICHE.upper()} END CUSTOMER RESULTS:")
        print(f"  🎯 Total unique leads: {len(unique_results)}")
        print(f"  💎 Premium quality: {quality_counts.get('premium', 0)}")
        print(f"  ⭐ Standard quality: {quality_counts.get('standard', 0)}")
        print(f"  📈 Volume quality: {quality_counts.get('volume', 0)}")
        print(f"  🚫 Excluded accounts: {excluded_count}")
        print(f"  🎯 Niche: {NICHE}")
        
        print(f"\n📚 CONTENT FOCUS BREAKDOWN:")
        for focus_type, count in focus_counts.items():
            print(f"  📖 {focus_type}: {count}")
        
        return unique_results
    else:
        print(f"\n❌ No {NICHE} end customers extracted")
        return []

def main():
    """Main Medium end customer scraper with smart user-aware deduplication"""
    
    estimated_leads = MAX_ARTICLES_TO_CHECK * 3  # Conservative estimate
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, CURRENT_SEARCH)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    with sync_playwright() as p:
        print(f"🎯 Launching Medium {NICHE.upper()} END CUSTOMER scraper...")
        
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Create context with or without authentication
        if storage_state:
            context = browser.new_context(
                storage_state=storage_state,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        else:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        
        page = context.new_page()
        
        try:
            # Navigate to Medium search for niche end customer content
            search_url = f"https://medium.com/search?q={CURRENT_SEARCH.replace(' ', '%20')}"
            print(f"🎯 Searching Medium for {NICHE} end customer content: '{CURRENT_SEARCH}'")
            print(f"📍 URL: {search_url}")
            print(f"🎯 Search type: Looking for {NICHE} content that attracts end customers")
            print(f"💡 Strategy: Articles about {NICHE} topics attract people interested in {NICHE} = potential customers")
            
            page.goto(search_url, timeout=EXTRACTION_TIMEOUT * 1000)
            time.sleep(3)
            
            # Enhanced scrolling for article results
            print(f"📜 Scrolling {MAX_SCROLLS} times to load more articles...")
            for i in range(MAX_SCROLLS):
                print(f"  🔄 Scroll {i + 1}/{MAX_SCROLLS}")
                
                page.mouse.wheel(0, 1200)
                time.sleep(random.uniform(DELAY_BETWEEN_SCROLLS, DELAY_BETWEEN_SCROLLS + 1))
                
                # Extended pause every 3 scrolls
                if (i + 1) % 3 == 0:
                    print(f"    ⏳ Extended pause for content loading...")
                    time.sleep(random.uniform(2, 4))
            
            print("⏳ Final content stabilization...")
            time.sleep(3)
            
            # Extract niche end customers from search results (raw leads)
            raw_leads = extract_medium_niche_customers(page)
            
            if not raw_leads:
                print("❌ No raw leads extracted")
                browser.close()
                return []

            # 🚀 APPLY SMART USER-AWARE DEDUPLICATION
            print(f"\n🧠 Applying deduplication strategy: {DEDUP_MODE}")
            print(f"👤 User-specific deduplication for: {username}")
            
            if SMART_DEDUP_AVAILABLE and DEDUP_MODE == "smart_user_aware":
                unique_leads, dedup_stats = process_leads_with_smart_deduplication(
                    raw_leads=raw_leads,
                    username=username,
                    platform=PLATFORM_NAME
                )
            elif SMART_DEDUP_AVAILABLE:
                # Use configuration-based deduplication
                mode_mapping = {
                    "keep_all": DeduplicationMode.KEEP_ALL,
                    "session_only": DeduplicationMode.SESSION_ONLY,
                    "smart_user_aware": DeduplicationMode.SMART_USER_AWARE,
                    "aggressive": DeduplicationMode.AGGRESSIVE
                }
                mode = mode_mapping.get(DEDUP_MODE, DeduplicationMode.SMART_USER_AWARE)
                unique_leads, raw_leads_copy, dedup_stats = apply_deduplication_strategy(
                    raw_leads, username, PLATFORM_NAME, mode
                )
            else:
                # Fallback to simple deduplication
                print("📋 Using basic deduplication (smart dedup not available)")
                unique_leads = []
                seen_names = set()
                for lead in raw_leads:
                    name_key = lead.get('name', '').lower().strip()
                    if name_key not in seen_names and len(name_key) > 1:
                        unique_leads.append(lead)
                        seen_names.add(name_key)
                dedup_stats = {"basic": True, "kept": len(unique_leads)}
            
            # Final results summary
            print(f"\n📊 FINAL RESULTS SUMMARY:")
            print(f"  📥 Raw leads extracted: {len(raw_leads)}")
            print(f"  ✅ Unique leads after dedup: {len(unique_leads)}")
            print(f"  📈 Efficiency: {(len(unique_leads) / len(raw_leads) * 100):.1f}% kept")
            print(f"  👤 User: {username}")
            print(f"  🔄 Dedup mode: {DEDUP_MODE}")
            print(f"  📊 Articles processed: {MAX_ARTICLES_TO_CHECK}")
            print(f"  🎯 Niche: {NICHE}")
            
            if len(unique_leads) > 30:
                print(f"🎉 EXCELLENT: {len(unique_leads)} leads (target exceeded!)")
            elif len(unique_leads) > 15:
                print(f"✅ GOOD: {len(unique_leads)} leads")
            elif len(unique_leads) > 8:
                print(f"⚠️ MODERATE: {len(unique_leads)} leads")
            else:
                print(f"⚠️ LOW: {len(unique_leads)} leads")
            
            leads = unique_leads

            # Finalize results with usage tracking
            if leads:
                try:
                    finalized_leads = finalize_scraper_results(PLATFORM_NAME, leads, CURRENT_SEARCH, username)
                    leads = finalized_leads
                    print("✅ Results finalized and usage tracked")
                except Exception as e:
                    print(f"⚠️ Error finalizing results: {e}")
            
            # Save results to multiple files
            if leads or (raw_leads and SAVE_RAW_LEADS):
                output_file = f"medium_{NICHE}_customers_{username}_{timestamp}.csv"
                
                fieldnames = [
                    'name', 'handle', 'bio', 'url', 'platform',
                    'customer_type', 'lead_quality', 'search_source',
                    'content_focus', 'transformation_stage', 'niche_goals',
                    'pain_points', 'reading_patterns', 'urgency_level',
                    'content_engagement', 'source_type', 'article_context',
                    'comment_preview', 'followers', 'location', 'search_term',
                    'extraction_method', 'relevance_score', 'source_article_url'
                ]
                
                files_saved = save_leads_to_files(
                    leads=leads,
                    raw_leads=raw_leads,
                    username=username,
                    timestamp=timestamp,
                    platform_name=PLATFORM_NAME,
                    csv_dir=CSV_DIR,          # uses your existing location
                    save_raw=SAVE_RAW_LEADS,  # if you have this flag
)
                
                # Save processed results to main CSV
                if leads:
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(leads)
                    files_saved.append(output_file)
                
                # Save raw results if enabled and different from processed
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    raw_filename = f"medium_{NICHE}_customers_raw_{username}_{timestamp}.csv"
                    raw_path = CSV_DIR / raw_filename
                    with open(raw_filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(raw_leads)
                    files_saved.append(raw_filename)
                    print(f"📋 Raw leads saved to {raw_filename}")
                
                print(f"\n✅ Successfully saved {len(leads)} {NICHE.upper()} END CUSTOMERS")
                print(f"🔍 Files saved: {', '.join(files_saved)}")
                print(f"🎯 Performance target: 15+ leads - {'✅ ACHIEVED' if len(leads) >= 15 else '❌ MISSED'}")
                
                # Upload to Google Sheets
                try:
                    from sheets_writer import write_leads_to_google_sheet
                    from daily_emailer import send_daily_leads_email
                    
                    sheet_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    print(f"📝 Writing Medium {NICHE} customers to Google Sheets...")
                    write_leads_to_google_sheet(leads)
                    print(f"✅ Successfully uploaded Medium {NICHE} customers to Google Sheets")
                    
                    print(f"📤 Sending Medium {NICHE} leads via email...")
                    send_daily_leads_email()
                    print(f"✅ Medium {NICHE} customer leads email sent!")
                    
                except ImportError:
                    print("📦 sheets_writer.py or daily_emailer.py not found - export features skipped")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                # Show niche customer samples
                if leads:
                    print(f"\n🎯 {NICHE.upper()} CUSTOMER SAMPLES:")
                    for i, lead in enumerate(leads[:5]):
                        print(f"  {i+1}. {lead['name']} ({lead['lead_quality']} quality)")
                        print(f"     Focus: {lead['content_focus']} | Stage: {lead['transformation_stage']}")
                        print(f"     Goals: {lead['niche_goals']}")
                        print(f"     Source: {lead['source_type']}")
                        print(f"     Article: {lead['article_context'][:50]}...")
                        print(f"     Search: {lead['search_source']}")
                        print()
                
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    print(f"\n📋 Raw leads preserved: {len(raw_leads)} total")
                    
            else:
                print(f"⚠️ No Medium {NICHE} customers extracted")
                leads = []
                
        except Exception as e:
            print(f"🚨 Medium scraper error: {e}")
            import traceback
            traceback.print_exc()
            leads = []
        finally:
            print("🔍 Keeping browser open for 3 seconds...")
            time.sleep(3)
            browser.close()
            
        return leads

if __name__ == "__main__":
    print(f"🎯 Medium {NICHE.upper()} END CUSTOMER Scraper - Smart Deduplication Version")
    print(f"🔍 Target: People who READ/WRITE about {NICHE} struggles & solutions")
    print(f"🚫 Exclude: {NICHE} professionals/coaches")
    print(f"🔍 Search term: '{CURRENT_SEARCH}' {'(from config)' if config.get('search_term') else '(fallback)'}")
    print(f"📰 Stay on search results page (no random clicking)")
    print(f"⏱️ Delay between scrolls: {DELAY_BETWEEN_SCROLLS}s")
    print(f"🛡️ Features:")
    print(f"  • Smart user-aware deduplication")
    print(f"  • Universal niche support")
    print(f"  • Enhanced result tracking")
    print(f"  • Raw lead preservation")
    print(f"  • Config-driven search terms")
    print(f"📚 Medium-specific features:")
    print(f"  • Search results analysis only")
    print(f"  • Author journey identification")
    print(f"  • Article title/preview analysis")
    print(f"  • No navigation to individual articles")
    print()
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print(f"🎯 Niche: {NICHE}")
    print()
    
    results = main()
    
    if results and len(results) >= 15:
        print(f"🎉 MEDIUM SUCCESS: Medium {NICHE} customer scraper completed with {len(results)} end customer leads!")
    elif results:
        print(f"✅ Medium {NICHE} customer scraper completed with {len(results)} leads")
    else:
        print(f"❌ Medium {NICHE} customer scraper completed with 0 leads")