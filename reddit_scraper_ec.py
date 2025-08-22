from datetime import datetime, timedelta
import time
from playwright.sync_api import sync_playwright
import pandas as pd
import json
import csv
import re
import random
from dm_sequences import generate_dm_with_fallback
import os

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

PLATFORM_NAME = "reddit"

# Load Reddit session state
try:
    with open("reddit_auth.json", "r") as f:
        storage_state = json.load(f)
except FileNotFoundError:
    print("⚠️ reddit_auth.json not found - continuing without authentication")
    storage_state = None

# Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = config_loader.get_platform_config('reddit')

# 🎯 UNIVERSAL NICHE CONFIGURATION
NICHE = config.get("niche", "fitness")  # Default to fitness if not configured

# 🎯 UNIVERSAL END CUSTOMER SEARCH TERMS BY NICHE (Reddit-specific)
NICHE_CUSTOMER_REDDIT_SEARCHES = {
    'fitness': [
        # Transformation Content (Premium Leads - $50-200 each)
        "weight loss progress pics",
        "before and after transformation",
        "my fitness journey reddit", 
        "lost weight finally",
        "body transformation update",
        
        # Beginner Content (Standard Leads - $20-50 each)
        "fitness beginner help",
        "new to gym anxiety",
        "starting fitness journey",
        "workout for complete beginner",
        "never exercised before",
        
        # Struggle/Help Content (High Converting - $30-100 each)
        "can't lose weight help",
        "fitness plateau stuck",
        "need motivation accountability",
        "workout not working",
        "fitness advice needed",
        
        # Equipment/Product Content (Volume Leads - $10-30 each)
        "home gym equipment recommendations",
        "best fitness apps reddit",
        "workout gear reviews",
        "supplement recommendations",
        "fitness tracker worth it",
        
        # Mom/Demographic Content (High Converting - $40-120 each)
        "mom fitness journey",
        "postpartum weight loss",
        "busy parent workout",
        "fitness over 40 reddit",
        "working mom exercise"
    ],
    'health': [
        "natural anxiety relief reddit",
        "chronic pain management help",
        "autoimmune disease support",
        "depression recovery story",
        "gut health transformation",
        "thyroid issues help",
        "chronic fatigue advice",
        "natural healing journey",
        "holistic health approach",
        "functional medicine experience"
    ],
    'business': [
        "startup failure lessons",
        "entrepreneurship journey reddit",
        "small business struggling",
        "freelance advice needed",
        "side hustle success story",
        "business idea feedback",
        "entrepreneur burnout help",
        "passive income reality",
        "first business mistakes",
        "bootstrapping startup advice"
    ],
    'tech': [
        "career change to tech",
        "self taught programmer journey", 
        "coding bootcamp experience",
        "first tech job search",
        "imposter syndrome tech",
        "learning programming help",
        "tech interview preparation",
        "web development beginner",
        "programming language choice",
        "tech industry advice"
    ],
    'beauty': [
        "skincare routine help",
        "acne transformation story",
        "anti aging skincare advice",
        "makeup beginner tips",
        "hair loss solutions reddit",
        "natural beauty routine",
        "skincare product recommendations",
        "beauty on budget advice",
        "sensitive skin help",
        "skincare transformation pics"
    ],
    'finance': [
        "paying off debt journey",
        "budgeting for beginners help",
        "investing advice needed",
        "financial planning basics",
        "emergency fund help",
        "credit score improvement",
        "money management tips",
        "frugal living advice",
        "retirement planning help",
        "financial freedom journey"
    ],
    'real_estate': [
        "first time home buyer help",
        "real estate investing advice",
        "house flipping experience",
        "rental property questions",
        "real estate market analysis",
        "property management tips",
        "real estate agent advice",
        "home buying process help",
        "real estate investment beginner",
        "property investment advice"
    ],
    'relationships': [
        "relationship advice reddit",
        "dating after divorce",
        "toxic relationship recovery",
        "communication in relationships",
        "marriage counseling help",
        "dating anxiety advice",
        "relationship boundaries help",
        "breakup recovery support",
        "self love journey",
        "attachment styles help"
    ]
}

# 🎯 UNIVERSAL END CUSTOMER SUBREDDITS BY NICHE
NICHE_END_CUSTOMER_SUBREDDITS = {
    'fitness': [
        'loseit', 'progresspics', 'getmotivated', 'NoStupidQuestions',
        'fitness', 'xxfitness', 'fitness30plus', 'bodyweightfitness',
        'MomForAMinute', 'daddit', 'StudentAthlete', 'seniors',
        'EOOD', 'DecidingToBeBetter', 'getdisciplined'
    ],
    'health': [
        'HealthAnxiety', 'ChronicPain', 'autoimmune', 'depression',
        'Anxiety', 'ADHD', 'mentalhealth', 'Narcolepsy',
        'ChronicIllness', 'migraine', 'Fibromyalgia', 'insomnia'
    ],
    'business': [
        'Entrepreneur', 'smallbusiness', 'startups', 'freelance',
        'WorkOnline', 'sidehustle', 'passive_income', 'business',
        'marketing', 'sales', 'selfimprovement', 'getmotivated'
    ],
    'tech': [
        'learnprogramming', 'cscareerquestions', 'webdev', 'coding',
        'ITCareerQuestions', 'careerchange', 'MachineLearning',
        'datascience', 'javascript', 'Python', 'webdevelopment'
    ],
    'beauty': [
        'SkincareAddiction', 'AsianBeauty', 'MakeupAddiction', 'acne',
        '30PlusSkinCare', 'SkincareAddicts', 'beauty', 'HaircareScience',
        'MakeupRehab', 'BeautyBoxes', 'SkincareAddictionLux'
    ],
    'finance': [
        'personalfinance', 'povertyfinance', 'financialindependence',
        'investing', 'stocks', 'SecurityAnalysis', 'ValueInvesting',
        'fire', 'frugal', 'budget', 'DaveRamsey', 'student loans'
    ],
    'real_estate': [
        'RealEstate', 'realestateinvesting', 'FirstTimeHomeBuyer',
        'Landlord', 'realtors', 'HomeImprovement', 'Mortgages',
        'PropertyManagement', 'REBubble', 'RealEstatePhotography'
    ],
    'relationships': [
        'relationship_advice', 'dating_advice', 'relationships',
        'dating', 'marriage', 'DeadBedrooms', 'survivinginfidelity',
        'BreakUps', 'ExNoContact', 'socialskills', 'confidence'
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
        fallback_term = random.choice(NICHE_CUSTOMER_REDDIT_SEARCHES.get(NICHE, NICHE_CUSTOMER_REDDIT_SEARCHES['fitness']))
        print(f"🎯 No search term in config - using fallback: '{fallback_term}'")
        return fallback_term

CURRENT_SEARCH = get_search_term_from_config()

# Get niche-specific subreddits
END_CUSTOMER_SUBREDDITS = NICHE_END_CUSTOMER_SUBREDDITS.get(NICHE, NICHE_END_CUSTOMER_SUBREDDITS['fitness'])

# Extract config values
MAX_SCROLLS = config["max_scrolls"]
DELAY_MIN = config.get("delay_min", 5)  # Longer delays for Reddit
DELAY_MAX = config.get("delay_max", 12)
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 45000)

# Reddit-specific config
MAX_POSTS_TO_CHECK = 20  # Number of posts to analyze
MAX_COMMENTS_PER_POST = 100  # Max comments to analyze per post
MAX_SUBREDDITS = 3  # Limit subreddit checks

# 🚀 Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")
SAVE_RAW_LEADS = config.get("save_raw_leads", True)

# 🚀 NEW: Show excluded accounts info
excluded_accounts = config_loader.get_excluded_accounts('reddit')
print(f"📋 Reddit {NICHE.title()} End Customer Config Loaded:")
print(f"  🎯 Search Term: '{CURRENT_SEARCH}' {'(from config)' if config.get('search_term') else '(fallback)'}")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  📝 Max Posts: {MAX_POSTS_TO_CHECK}")
print(f"  💬 Max Comments/Post: {MAX_COMMENTS_PER_POST}")
print(f"  📍 End Customer Subreddits: {len(END_CUSTOMER_SUBREDDITS)}")
print(f"  ⏱️ Delay Range: {DELAY_MIN}-{DELAY_MAX}s")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
print(f"  🎯 Niche: {NICHE}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")

def update_last_run_time():
    """Update the last run time for Reddit scraper"""
    data = {"last_run": datetime.now().isoformat()}
    with open("reddit_last_run.json", "w") as f:
        json.dump(data, f)

def is_niche_end_customer_reddit(username, post_title, post_content, comment_text="", niche=None):
    """
    🎯 Universal function to determine if Reddit user is END CUSTOMER vs professional
    
    Reddit context: Focus on help-seeking posts, questions, transformation shares
    UPDATED: More inclusive detection for better lead capture
    """
    if niche is None:
        niche = NICHE
        
    analysis_text = f"{username} {post_title} {post_content} {comment_text}".lower()
    
    # 🚫 EXCLUDE PROFESSIONALS (stricter criteria but niche-aware)
    professional_indicators = [
        f'{niche} coach', f'{niche} trainer', f'{niche} consultant',
        'personal trainer', 'certified trainer', 'coaching services',
        'dm for coaching', 'trainer here', 'professional', 'expert',
        'check out my program', 'my coaching business', 'offering training',
        'i coach', 'i train clients', 'as a trainer', 'as a coach',
        'my services', 'contact me for', 'consultation available'
    ]
    
    professional_count = 0
    for indicator in professional_indicators:
        if indicator in analysis_text:
            professional_count += 1
    
    # Only exclude if multiple professional indicators (be less strict)
    if professional_count >= 2:
        return False, 0, "professional"
    
    # 🎯 UNIVERSAL END CUSTOMER SIGNALS (more inclusive)
    end_customer_signals = {
        # Premium Leads ($50-200 each) - High intent help seeking
        'help_seeking': [
            'need help', 'please help', 'advice needed', 'what should i do',
            'how do i', 'can someone help', 'desperate', 'stuck', 'lost',
            'dont know', 'confused', 'guidance', 'suggestions', 'tips'
        ],
        
        # Premium Leads - Transformation sharing/documenting
        'transformation_sharing': [
            'progress', 'before and after', 'transformation', 'lost',
            'finally', 'achievement', 'goal', 'success', 'journey',
            'update', 'pics', 'photo', 'my story', 'my experience'
        ],
        
        # Premium Leads - Struggle/plateau content
        'struggle_plateau': [
            'plateau', 'stuck', 'not losing', 'not working', 'frustrated',
            'tried everything', 'months', 'nothing works', 'same',
            'discouraged', 'giving up', 'failed', 'struggling'
        ],
        
        # Standard Leads ($20-50 each) - Beginner questions
        'beginner_questions': [
            'beginner', 'new to', 'first time', 'never done', 'start',
            'where to begin', 'newbie', 'noob', 'just started', 'day 1',
            'week 1', 'complete beginner', 'total beginner'
        ],
        
        # Standard Leads - Goal setting
        'goal_oriented': [
            'goal', 'trying to', 'want to', 'hoping to', 'plan to',
            'working towards', 'target', 'aiming for', 'my plan'
        ],
        
        # Volume Leads ($10-30 each) - Product/equipment questions
        'product_interest': [
            'recommend', 'best', 'should i buy', 'worth it', 'review',
            'equipment', 'app', 'supplement', 'product', 'gear',
            'what do you think', 'opinions', 'experiences'
        ],
        
        # Volume Leads - General motivation/support
        'motivation_support': [
            'motivation', 'support', 'accountability', 'encourage',
            'keep going', 'anyone else', 'same boat', 'relate',
            'similar experience', 'community'
        ],
        
        # NEW: Common Reddit customer language
        'reddit_language': [
            'guys', 'everyone', 'people', 'anyone', 'somebody',
            'this sub', 'reddit', 'community', 'posted', 'sharing',
            'update', 'rant', 'confession', 'honest', 'real talk'
        ]
    }
    
    # Score customer signals with LOWER thresholds for better capture
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
            
            if signal_type in ['help_seeking', 'transformation_sharing', 'struggle_plateau']:
                total_score += category_score * 3  # Reduced from 4
                customer_type = "premium"
            elif signal_type in ['beginner_questions', 'goal_oriented']:
                total_score += category_score * 2
                if customer_type != "premium":
                    customer_type = "standard"
            else:  # product_interest, motivation_support, reddit_language
                total_score += category_score
    
    # LOWERED THRESHOLD: Accept with score >= 1
    is_customer = total_score >= 1
    
    # BONUS: Extra points for niche-related content context
    niche_keywords = {
        'fitness': ['weight', 'lose', 'gain', 'muscle', 'gym', 'workout', 'exercise', 'diet', 'fitness', 'health'],
        'health': ['health', 'anxiety', 'depression', 'chronic', 'pain', 'recovery', 'healing', 'wellness'],
        'business': ['business', 'startup', 'entrepreneur', 'money', 'income', 'career', 'job', 'freelance'],
        'tech': ['coding', 'programming', 'tech', 'software', 'development', 'career', 'job', 'bootcamp'],
        'beauty': ['skin', 'makeup', 'beauty', 'hair', 'acne', 'skincare', 'cosmetics', 'appearance'],
        'finance': ['money', 'debt', 'budget', 'invest', 'financial', 'save', 'credit', 'income'],
        'real_estate': ['house', 'home', 'property', 'real estate', 'mortgage', 'rent', 'buy', 'invest'],
        'relationships': ['relationship', 'dating', 'marriage', 'love', 'partner', 'boyfriend', 'girlfriend']
    }
    
    current_keywords = niche_keywords.get(niche, niche_keywords['fitness'])
    niche_context_bonus = 0
    for keyword in current_keywords:
        if keyword in analysis_text:
            niche_context_bonus += 0.5
    
    total_score += niche_context_bonus
    
    # If we have niche context but low score, still consider as end customer
    if niche_context_bonus >= 2 and total_score >= 1:
        is_customer = True
        if customer_type == "volume" and total_score < 3:
            customer_type = "standard"
    
    return is_customer, total_score, customer_type

def extract_reddit_customer_intelligence(username, post_title, post_content, comment_text="", niche=None):
    """
    🧠 Extract universal customer intelligence from Reddit data
    """
    if niche is None:
        niche = NICHE
        
    combined_text = f"{username} {post_title} {post_content} {comment_text}".lower()
    
    intelligence = {
        'post_type': 'general',
        'transformation_stage': 'unknown',
        'goals': [],
        'pain_points': [],
        'timeline': 'none',
        'product_interest': [],
        'support_seeking': 'unknown'
    }
    
    # Determine post type
    post_types = {
        'progress': ['progress', 'before and after', 'transformation', 'update', 'achievement'],
        'question': ['help', 'advice', 'question', 'how', 'what', 'where', 'when', 'why'],
        'struggle': ['stuck', 'plateau', 'frustrated', 'not working', 'problem'],
        'beginner': ['beginner', 'new', 'first', 'start', 'newbie', 'noob'],
        'motivation': ['motivation', 'support', 'accountability', 'encourage']
    }
    
    for post_type, keywords in post_types.items():
        if any(keyword in combined_text for keyword in keywords):
            intelligence['post_type'] = post_type
            break
    
    # Determine transformation stage
    stage_indicators = {
        'just_starting': ['day 1', 'week 1', 'just started', 'beginning', 'new to'],
        'early_progress': ['week 2', 'month 1', 'first month', 'early progress'],
        'mid_journey': ['month 2', 'month 3', 'halfway', 'been at it'],
        'plateau': ['plateau', 'stuck', 'not progressing', 'same'],
        'success': ['goal reached', 'finally', 'success story', 'made it']
    }
    
    for stage, indicators in stage_indicators.items():
        if any(indicator in combined_text for indicator in indicators):
            intelligence['transformation_stage'] = stage
            break
    
    # Extract goals (niche-specific)
    niche_goals = {
        'fitness': ['lose weight', 'build muscle', 'get stronger', 'run marathon', 'abs', 'toned'],
        'health': ['reduce anxiety', 'manage pain', 'heal naturally', 'improve energy', 'sleep better'],
        'business': ['start business', 'make money', 'quit job', 'financial freedom', 'passive income'],
        'tech': ['learn coding', 'career change', 'build app', 'get job', 'freelance'],
        'beauty': ['clear skin', 'anti aging', 'look younger', 'hair growth', 'natural beauty'],
        'finance': ['pay off debt', 'save money', 'invest', 'budget better', 'financial security'],
        'real_estate': ['buy house', 'invest property', 'flip houses', 'rental income'],
        'relationships': ['find love', 'save marriage', 'better communication', 'heal trauma']
    }
    
    for goal in niche_goals.get(niche, []):
        if goal in combined_text:
            intelligence['goals'].append(goal)
    
    # Extract pain points (universal)
    pain_indicators = [
        'no time', 'too busy', 'no motivation', 'too tired', 'no energy',
        'expensive', 'no money', 'at home', 'social anxiety', 'self conscious',
        'confused', 'overwhelmed', 'frustrated', 'stuck', 'plateaued'
    ]
    
    for pain in pain_indicators:
        if pain in combined_text:
            intelligence['pain_points'].append(pain)
    
    # Extract product interest (niche-specific)
    niche_products = {
        'fitness': ['home gym', 'dumbbells', 'resistance bands', 'yoga mat', 'fitness tracker', 'app'],
        'health': ['supplements', 'vitamins', 'probiotics', 'essential oils', 'natural remedies'],
        'business': ['course', 'coaching', 'software', 'tools', 'books', 'mastermind'],
        'tech': ['course', 'bootcamp', 'laptop', 'software', 'books', 'tutorials'],
        'beauty': ['skincare', 'serum', 'moisturizer', 'makeup', 'tools', 'treatments'],
        'finance': ['course', 'book', 'app', 'software', 'advisor', 'planner'],
        'real_estate': ['course', 'coaching', 'software', 'books', 'mentorship'],
        'relationships': ['therapy', 'coaching', 'course', 'book', 'workshop']
    }
    
    for product in niche_products.get(niche, []):
        if product in combined_text:
            intelligence['product_interest'].append(product)
    
    # Determine support seeking level
    support_indicators = {
        'high': ['accountability', 'buddy', 'group', 'support', 'help me'],
        'medium': ['advice', 'suggestions', 'tips', 'recommendations'],
        'low': ['sharing', 'update', 'progress', 'just wanted to say']
    }
    
    for level, indicators in support_indicators.items():
        if any(indicator in combined_text for indicator in indicators):
            intelligence['support_seeking'] = level
            break
    
    return intelligence

def search_reddit_end_customers(page, search_term):
    """Search Reddit for end customer content in specific subreddits - IMPROVED"""
    print(f"🔍 Searching Reddit for {NICHE} end customers: '{search_term}'")
    
    all_posts = []
    
    # Try targeted subreddit search first
    for i, subreddit in enumerate(END_CUSTOMER_SUBREDDITS[:MAX_SUBREDDITS]):
        print(f"\n📍 Searching r/{subreddit} ({i+1}/{MAX_SUBREDDITS})")
        
        try:
            # IMPROVED: Try multiple search approaches for each subreddit
            search_urls = [
                # Search within subreddit
                f"https://www.reddit.com/r/{subreddit}/search/?q={search_term.replace(' ', '%20')}&restrict_sr=1&sort=relevance&t=month",
                # Hot posts in subreddit (fallback)
                f"https://www.reddit.com/r/{subreddit}/hot/",
                # New posts in subreddit (fallback)
                f"https://www.reddit.com/r/{subreddit}/new/"
            ]
            
            for j, url in enumerate(search_urls):
                try:
                    print(f"    🌐 Attempt {j+1}: {url[:50]}...")
                    
                    page.goto(url, timeout=30000)
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                    
                    # Handle any access issues after navigation
                    handle_reddit_access_issues(page)
                    
                    # Check if page loaded successfully
                    page_title = page.title()
                    page_text = page.inner_text('body').lower()
                    
                    print(f"    📄 Page title: {page_title[:50]}...")
                    
                    # Check for Reddit errors
                    if any(error in page_text for error in ['blocked', 'forbidden', 'private', 'quarantined']):
                        print(f"    ⚠️ Access issue detected, trying next approach...")
                        continue
                    
                    # Check if we're actually on Reddit
                    if 'reddit' not in page_title.lower() and 'reddit' not in page.url.lower():
                        print(f"    ⚠️ Not on Reddit page, trying next approach...")
                        continue
                    
                    # Extract posts from this attempt
                    subreddit_posts = extract_posts_from_search(page, subreddit)
                    
                    if subreddit_posts:
                        all_posts.extend(subreddit_posts)
                        print(f"    ✅ Success! Found {len(subreddit_posts)} posts in r/{subreddit}")
                        break  # Success, move to next subreddit
                    else:
                        print(f"    ❌ No posts extracted, trying next approach...")
                        
                except Exception as e:
                    print(f"    ❌ Error with approach {j+1}: {e}")
                    continue
            
            # Delay between subreddits
            if i < len(END_CUSTOMER_SUBREDDITS[:MAX_SUBREDDITS]) - 1:
                time.sleep(random.uniform(5, 10))
                
        except Exception as e:
            print(f"  ❌ Error searching r/{subreddit}: {e}")
            continue
    
    # If no posts found, try general search with different approaches
    if not all_posts:
        print(f"\n🔍 No posts from subreddits, trying general Reddit search...")
        
        general_search_urls = [
            f"https://www.reddit.com/search/?q={search_term.replace(' ', '%20')}&sort=relevance&t=month",
            f"https://www.reddit.com/search/?q={search_term.replace(' ', '%20')}&sort=hot&t=week",
            f"https://www.reddit.com/search/?q={search_term.replace(' ', '%20')}&sort=new&t=week"
        ]
        
        for i, url in enumerate(general_search_urls):
            try:
                print(f"    🌐 General search {i+1}: {url[:60]}...")
                
                page.goto(url, timeout=30000)
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                
                # Check page status
                page_title = page.title()
                print(f"    📄 Page title: {page_title[:50]}...")
                
                general_posts = extract_posts_from_search(page, "general")
                
                if general_posts:
                    all_posts.extend(general_posts)
                    print(f"    ✅ General search found {len(general_posts)} posts")
                    break
                else:
                    print(f"    ❌ No posts from general search {i+1}")
                    
            except Exception as e:
                print(f"    ❌ General search {i+1} failed: {e}")
                continue
    
    # Final fallback: Try popular subreddits directly
    if not all_posts:
        print(f"\n🔍 Final fallback: Checking popular {NICHE} subreddits directly...")
        
        fallback_subreddits = END_CUSTOMER_SUBREDDITS[:3]  # Use first 3 niche subreddits
        
        for subreddit in fallback_subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot/"
                print(f"    🌐 Fallback: {url}")
                
                page.goto(url, timeout=30000)
                time.sleep(random.uniform(3, 6))
                
                fallback_posts = extract_posts_from_search(page, subreddit)
                
                if fallback_posts:
                    all_posts.extend(fallback_posts)
                    print(f"    ✅ Fallback found {len(fallback_posts)} posts in r/{subreddit}")
                    break
                    
            except Exception as e:
                print(f"    ❌ Fallback failed for r/{subreddit}: {e}")
                continue
    
    print(f"\n📊 Search Summary:")
    print(f"  🎯 Total posts found: {len(all_posts)}")
    print(f"  📝 Posts to analyze: {min(len(all_posts), MAX_POSTS_TO_CHECK)}")
    
    return all_posts[:MAX_POSTS_TO_CHECK]

def extract_posts_from_search(page, subreddit):
    """Extract posts from Reddit search results - UPDATED for current Reddit"""
    posts = []
    
    try:
        print(f"    📋 Analyzing search results page...")
        
        # Take screenshot for debugging
        try:
            page.screenshot(path=f"reddit_search_debug_{subreddit}.png", timeout=5000)
            print(f"    📸 Debug screenshot: reddit_search_debug_{subreddit}.png")
        except:
            pass
        
        # Wait for content to load
        time.sleep(5)
        
        # Scroll to load more posts
        for i in range(min(3, MAX_SCROLLS)):
            page.mouse.wheel(0, 800)
            time.sleep(random.uniform(2, 4))
        
        # UPDATED: Modern Reddit selectors
        post_selectors = [
            # New Reddit selectors
            'article[data-testid*="post"]',
            'div[data-testid*="post"]',
            '[data-redditid]',
            'div[data-click-id="body"]',
            
            # Post containers
            'div[class*="Post"]',
            'div[class*="thing"]',
            'div[class*="search-result"]',
            
            # Fallback - any clickable post links
            'a[href*="/comments/"]',
            'h3 a[href*="/r/"]'
        ]
        
        post_links = []
        working_selector = None
        
        # Try to find post links instead of extracting content directly
        for selector in post_selectors:
            try:
                if 'a[href' in selector:
                    # For link selectors, get the URLs directly
                    elements = page.query_selector_all(selector)
                    if len(elements) > 0:
                        for element in elements[:MAX_POSTS_TO_CHECK]:
                            href = element.get_attribute('href')
                            if href and '/comments/' in href:
                                full_url = f"https://www.reddit.com{href}" if href.startswith('/') else href
                                post_links.append(full_url)
                        
                        if post_links:
                            working_selector = selector
                            print(f"    ✅ Found {len(post_links)} post links using: {selector}")
                            break
                else:
                    # For container selectors, look for links within them
                    containers = page.query_selector_all(selector)
                    if len(containers) > 0:
                        for container in containers[:MAX_POSTS_TO_CHECK]:
                            try:
                                link_el = container.query_selector('a[href*="/comments/"]')
                                if link_el:
                                    href = link_el.get_attribute('href')
                                    if href:
                                        full_url = f"https://www.reddit.com{href}" if href.startswith('/') else href
                                        post_links.append(full_url)
                            except:
                                continue
                        
                        if post_links:
                            working_selector = selector
                            print(f"    ✅ Found {len(post_links)} post links in containers: {selector}")
                            break
            except Exception as e:
                continue
        
        # If no post links found, try text-based extraction
        if not post_links:
            print(f"    🔍 No post elements found, trying text-based extraction...")
            try:
                page_html = page.content()
                
                # Look for comment URLs in the HTML
                comment_pattern = r'href="(/r/\w+/comments/[^"]+)"'
                matches = re.findall(comment_pattern, page_html)
                
                for match in matches[:MAX_POSTS_TO_CHECK]:
                    post_links.append(f"https://www.reddit.com{match}")
                
                if post_links:
                    print(f"    ✅ Text extraction found {len(post_links)} post links")
            except:
                pass
        
        # If still no links, check if we're on the right page
        if not post_links:
            page_title = page.title()
            page_url = page.url
            print(f"    ❌ No posts found!")
            print(f"        Page title: {page_title}")
            print(f"        Page URL: {page_url}")
            return posts
        
        # Now visit each post individually to get full content
        print(f"    📖 Visiting {len(post_links)} individual posts...")
        
        for i, post_url in enumerate(post_links):
            if i >= MAX_POSTS_TO_CHECK:
                break
                
            try:
                print(f"      📄 Post {i+1}/{len(post_links)}: Visiting individual post...")
                
                # Visit the individual post
                page.goto(post_url, timeout=30000)
                time.sleep(random.uniform(3, 6))
                
                # Extract full post data from individual post page
                post_data = extract_full_post_data(page, post_url)
                
                if post_data:
                    post_data['subreddit'] = subreddit
                    posts.append(post_data)
                    print(f"        ✅ Extracted: {post_data.get('title', 'No title')[:40]}...")
                else:
                    print(f"        ❌ Could not extract post data")
                
                # Delay between posts
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"        ⚠️ Error visiting post {i+1}: {e}")
                continue
        
        print(f"    📊 Successfully extracted {len(posts)} posts from {subreddit}")
        return posts
        
    except Exception as e:
        print(f"    ❌ Error extracting posts: {e}")
        return posts

def extract_full_post_data(page, post_url):
    """Extract complete data from an individual Reddit post page"""
    try:
        post_data = {
            'title': '',
            'content': '',
            'author': '',
            'url': post_url,
            'score': 0,
            'comments_count': 0,
            'subreddit': ''
        }
        
        # Wait for page to load
        time.sleep(2)
        
        # Extract title - multiple strategies
        title_selectors = [
            'h1[data-testid="post-content"] span',
            'h1 span',
            '[data-test-id="post-content-title"]',
            'h1',
            '.Post-title h3',
            'div[data-click-id="title"] h3'
        ]
        
        for selector in title_selectors:
            try:
                title_el = page.query_selector(selector)
                if title_el:
                    title_text = title_el.inner_text().strip()
                    if len(title_text) > 5:  # Valid title
                        post_data['title'] = title_text
                        break
            except:
                continue
        
        # Extract author
        author_selectors = [
            '[data-testid="post-author-link"]',
            'a[href*="/user/"]',
            'a[href*="/u/"]',
            '.author',
            '[data-click-id="author"]'
        ]
        
        for selector in author_selectors:
            try:
                author_el = page.query_selector(selector)
                if author_el:
                    author_text = author_el.inner_text().strip()
                    # Clean up author name
                    if author_text.startswith('u/'):
                        post_data['author'] = author_text[2:]
                    elif author_text.startswith('/u/'):
                        post_data['author'] = author_text[3:]
                    else:
                        post_data['author'] = author_text
                    
                    # Validate author
                    if len(post_data['author']) > 2 and post_data['author'].lower() not in ['deleted', 'removed']:
                        break
            except:
                continue
        
        # Extract post content/text
        content_selectors = [
            '[data-testid="post-content"] div[data-click-id="text"]',
            'div[data-click-id="text"]',
            '.usertext-body .md',
            '.Post-body',
            'div[data-test-id="post-content-text"]'
        ]
        
        for selector in content_selectors:
            try:
                content_el = page.query_selector(selector)
                if content_el:
                    content_text = content_el.inner_text().strip()
                    if len(content_text) > 10:  # Valid content
                        post_data['content'] = content_text[:500]  # Limit length
                        break
            except:
                continue
        
        # Extract subreddit from URL if not in content
        try:
            subreddit_match = re.search(r'/r/([^/]+)/', post_url)
            if subreddit_match:
                post_data['subreddit'] = subreddit_match.group(1)
        except:
            pass
        
        # Validate that we have minimum required data
        if post_data['title'] and post_data['author'] and len(post_data['author']) > 2:
            return post_data
        else:
            print(f"        ❌ Missing required data - Title: {bool(post_data['title'])}, Author: {bool(post_data['author'])}")
            return None
        
    except Exception as e:
        print(f"        ❌ Error extracting full post data: {e}")
        return None

def analyze_post_for_end_customers(page, post_data):
    """Analyze a post and extract end customer leads - IMPROVED"""
    leads = []
    excluded_count = 0
    
    try:
        print(f"  📖 Analyzing: {post_data['title'][:50]}...")
        
        # Check if post author is an end customer
        author = post_data['author']
        title = post_data['title']
        content = post_data['content']
        
        # Skip deleted/removed users
        if author.lower() in ['deleted', 'removed', 'automoderator']:
            print(f"    ⏭️ Skipping deleted/removed author")
        else:
            print(f"    👤 Analyzing post author: u/{author}")
            print(f"    📝 Title: {title[:60]}...")
            print(f"    📄 Content: {content[:100] if content else 'No content'}...")
            
            # Analyze post author with detailed scoring
            is_customer, score, customer_type = is_niche_end_customer_reddit(
                author, title, content, "", NICHE
            )
            
            print(f"    📊 Author analysis: Customer={is_customer}, Score={score}, Type={customer_type}")
            
            if is_customer and score >= 1:
                # Check for exclusion
                if should_exclude_account(author, PLATFORM_NAME, config_loader):
                    excluded_count += 1
                    print(f"    🚫 Excluded: u/{author}")
                else:
                    # Extract intelligence
                    intelligence = extract_reddit_customer_intelligence(author, title, content, "", NICHE)
                    
                    # Create lead for post author
                    lead = create_reddit_end_customer_lead(
                        author, title, content, "", customer_type, score, intelligence, 
                        post_data.get('url', ''), 'post_author'
                    )
                    
                    if lead:
                        leads.append(lead)
                        print(f"    ✅ POST AUTHOR: u/{author} | {customer_type} | {intelligence['post_type']} | Score: {score}")
            else:
                print(f"    ⏭️ Author u/{author} not classified as end customer (score: {score})")
        
        # Always try to get comments (even if post author isn't end customer)
        if post_data.get('url'):
            try:
                print(f"    💬 Checking comments...")
                
                # Navigate to post if not already there
                current_url = page.url
                target_url = post_data['url']
                
                if current_url != target_url:
                    print(f"      🌐 Navigating to post...")
                    page.goto(target_url, timeout=30000)
                    time.sleep(random.uniform(3, 6))
                
                # Handle Reddit access issues
                handle_reddit_access_issues(page)
                
                comment_leads = extract_comments_from_post(page, post_data)
                
                if comment_leads:
                    leads.extend(comment_leads)
                    print(f"    💬 Found {len(comment_leads)} end customers in comments")
                else:
                    print(f"    💬 No end customers found in comments")
                
            except Exception as e:
                print(f"    ⚠️ Error getting comments: {e}")
        else:
            print(f"    ⚠️ No post URL available for comment extraction")
        
        print(f"    📊 Total leads from this post: {len(leads)}")
        return leads
        
    except Exception as e:
        print(f"    ❌ Error analyzing post: {e}")
        return leads

def extract_comments_from_post(page, post_data):
    """Extract end customer leads from post comments - IMPROVED"""
    comment_leads = []
    excluded_count = 0
    
    try:
        print(f"      💬 Loading comments...")
        
        # Wait longer for comments to load
        time.sleep(5)
        
        # Try to expand comments if there's a "load more" button
        try:
            load_more_selectors = [
                'button:has-text("load more")',
                'button:has-text("Show more")',
                'button:has-text("View more")',
                '[data-testid="load-more-comments"]'
            ]
            
            for selector in load_more_selectors:
                try:
                    load_button = page.query_selector(selector)
                    if load_button and load_button.is_visible():
                        print(f"      📖 Clicking load more comments...")
                        load_button.click()
                        time.sleep(3)
                        break
                except:
                    continue
        except:
            pass
        
        # Scroll down to load more comments
        for i in range(3):
            page.mouse.wheel(0, 800)
            time.sleep(2)
        
        # UPDATED: Modern Reddit comment selectors
        comment_selectors = [
            # New Reddit comment structure
            'div[data-testid*="comment"]',
            'div[class*="Comment"]',
            'div[class*="comment"]',
            
            # Alternative selectors
            '[data-test-id="comment"]', 
            'div[id*="comment"]',
            'article[role="article"]',
            
            # Fallback - any div that might contain comments
            'div:has-text("ago")',  # Comments usually have timestamps
            'div:has-text("reply")',  # Comments have reply buttons
        ]
        
        comment_elements = []
        working_selector = None
        
        for selector in comment_selectors:
            try:
                elements = page.query_selector_all(selector)
                print(f"        🔍 Selector '{selector}': found {len(elements)} elements")
                
                if len(elements) > 0:
                    # Filter for actual comments (must have meaningful text)
                    valid_comments = []
                    for element in elements:
                        try:
                            text = element.inner_text()
                            if (len(text) > 20 and  # Minimum comment length
                                'ago' in text and   # Has timestamp
                                len(text) < 2000):  # Not too long (avoid page content)
                                valid_comments.append(element)
                        except:
                            continue
                    
                    if len(valid_comments) >= 3:  # Need at least 3 valid comments
                        comment_elements = valid_comments[:MAX_COMMENTS_PER_POST]
                        working_selector = selector
                        print(f"        ✅ Using '{selector}': {len(comment_elements)} valid comments")
                        break
            except Exception as e:
                continue
        
        if not comment_elements:
            print(f"        ❌ No comment elements found with any selector")
            return comment_leads
        
        print(f"        📝 Processing {len(comment_elements)} comments...")
        
        processed_comments = 0
        for i, element in enumerate(comment_elements):
            if processed_comments >= MAX_COMMENTS_PER_POST:
                break
            
            try:
                # Extract comment data with improved methods
                comment_author = ""
                comment_text = ""
                
                # Get full element text first
                full_element_text = element.inner_text()
                lines = [line.strip() for line in full_element_text.split('\n') if line.strip()]
                
                # Extract author - look for patterns
                for line in lines:
                    # Look for username patterns
                    if (line.startswith('u/') or 
                        (len(line) >= 3 and len(line) <= 25 and 
                         line.replace('_', '').replace('-', '').isalnum())):
                        comment_author = line.replace('u/', '')
                        break
                
                # If no author found with patterns, try selectors
                if not comment_author:
                    author_selectors = [
                        'a[href*="/user/"]',
                        'a[href*="/u/"]',
                        '[data-testid*="author"]',
                        '.author'
                    ]
                    
                    for selector in author_selectors:
                        try:
                            author_el = element.query_selector(selector)
                            if author_el:
                                author_text = author_el.inner_text().strip()
                                comment_author = author_text.replace('u/', '')
                                break
                        except:
                            continue
                
                # Extract comment text - get meaningful content
                # Skip lines that are likely UI elements
                meaningful_lines = []
                for line in lines:
                    if (len(line) > 10 and  # Meaningful length
                        not line.startswith('u/') and  # Not username
                        'ago' not in line and  # Not timestamp
                        'reply' not in line.lower() and  # Not UI element
                        'vote' not in line.lower() and  # Not voting UI
                        'share' not in line.lower()):  # Not sharing UI
                        meaningful_lines.append(line)
                
                comment_text = ' '.join(meaningful_lines[:3])  # First 3 meaningful lines
                
                # Validate comment data
                if (comment_author and comment_text and 
                    len(comment_text) > 15 and 
                    len(comment_author) >= 3 and
                    comment_author.lower() not in ['deleted', 'removed', 'automoderator', 'automod']):
                    
                    print(f"          👤 u/{comment_author}: {comment_text[:50]}...")
                    
                    # Check if commenter is end customer
                    is_customer, score, customer_type = is_niche_end_customer_reddit(
                        comment_author, post_data['title'], post_data['content'], comment_text, NICHE
                    )
                    
                    if is_customer and score >= 1:
                        # Check for exclusion
                        if should_exclude_account(comment_author, PLATFORM_NAME, config_loader):
                            excluded_count += 1
                            print(f"            🚫 Excluded: u/{comment_author}")
                            continue
                        
                        # Extract intelligence
                        intelligence = extract_reddit_customer_intelligence(
                            comment_author, post_data['title'], post_data['content'], comment_text, NICHE
                        )
                        
                        # Create lead
                        lead = create_reddit_end_customer_lead(
                            comment_author, post_data['title'], post_data['content'], 
                            comment_text, customer_type, score, intelligence,
                            post_data.get('url', ''), 'commenter'
                        )
                        
                        if lead:
                            comment_leads.append(lead)
                            processed_comments += 1
                            print(f"            ✅ u/{comment_author} | {customer_type} | Score: {score}")
                    else:
                        print(f"            ⏭️ u/{comment_author} | Not end customer (score: {score})")
                else:
                    print(f"          ❌ Invalid comment data")
                
            except Exception as e:
                print(f"          ⚠️ Error processing comment {i+1}: {e}")
                continue
        
        print(f"        📊 Extracted {len(comment_leads)} end customer leads from comments")
        return comment_leads
        
    except Exception as e:
        print(f"      ❌ Error extracting comments: {e}")
        return comment_leads

def create_reddit_end_customer_lead(username, post_title, post_content, comment_text, 
                                   customer_type, score, intelligence, post_url, source_type):
    """Create a standardized Reddit end customer lead"""
    try:
        # Create display name
        name = username.replace('_', ' ').replace('-', ' ').title()
        if len(name) < 2:
            name = username
        
        handle = f"u/{username}"
        
        # Create bio from intelligence and content
        bio_parts = []
        if intelligence['post_type'] != 'general':
            bio_parts.append(f"{intelligence['post_type']} post")
        if intelligence['goals']:
            bio_parts.append(f"Goals: {', '.join(intelligence['goals'])}")
        if intelligence['transformation_stage'] != 'unknown':
            bio_parts.append(f"Stage: {intelligence['transformation_stage']}")
        
        bio = f"Reddit {source_type} - {', '.join(bio_parts)}" if bio_parts else f"Active Reddit {NICHE} community member"
        
        # Create lead
        lead = {
            "name": name,
            "handle": handle,
            "bio": bio[:200] + "..." if len(bio) > 200 else bio,
            "url": f"https://www.reddit.com/user/{username}",
            "platform": "reddit",
            
            # 🎯 UNIVERSAL CUSTOMER CLASSIFICATION
            "customer_type": f"{NICHE}_end_customer",
            "lead_quality": customer_type,
            "search_source": CURRENT_SEARCH,
            
            # 🧠 UNIVERSAL INTELLIGENCE
            "post_type": intelligence['post_type'],
            "transformation_stage": intelligence['transformation_stage'],
            "niche_goals": ", ".join(intelligence['goals']) if intelligence['goals'] else f"General {NICHE}",
            "pain_points": ", ".join(intelligence['pain_points']) if intelligence['pain_points'] else "None mentioned",
            "product_interest": ", ".join(intelligence['product_interest']) if intelligence['product_interest'] else "None mentioned",
            "support_seeking": intelligence['support_seeking'],
            "source_type": source_type,  # post_author or commenter
            
            # Content context
            "post_title": post_title[:100] + "..." if len(post_title) > 100 else post_title,
            "content_preview": (comment_text or post_content)[:150] + "..." if len(comment_text or post_content) > 150 else (comment_text or post_content),
            
            # Standard fields
            'title': f'Reddit {source_type} - {customer_type} lead',
            'location': 'Location not specified',
            'followers': 'Not available',
            'profile_url': f"https://www.reddit.com/user/{username}",
            'search_term': CURRENT_SEARCH,
            'extraction_method': f'Reddit {source_type}',
            'relevance_score': score,
            'source_post_url': post_url
        }
        
        return lead
        
    except Exception as e:
        print(f"    ❌ Error creating lead: {e}")
        return None

def extract_reddit_niche_customers(page):
    """Main function to extract niche end customers from Reddit - Universal version"""
    print(f"🎯 Extracting {NICHE} end customers from Reddit...")
    
    all_leads = []
    excluded_count = 0
    
    # Handle any initial access issues
    handle_reddit_access_issues(page)
    
    # Search for relevant posts
    posts = search_reddit_end_customers(page, CURRENT_SEARCH)
    
    if not posts:
        print("❌ No relevant posts found")
        print("💡 Troubleshooting suggestions:")
        print("   • Check if Reddit is accessible in your region")
        print("   • Try running with reddit_auth.json for better access")
        print("   • Reddit may be rate limiting - try again later")
        print("   • Search term may be too specific")
        return []
    
    print(f"📝 Analyzing {len(posts)} posts for {NICHE} end customers...")
    
    for i, post_data in enumerate(posts):
        print(f"\n📖 Post {i+1}/{len(posts)}")
        
        # Handle access issues before analyzing each post
        handle_reddit_access_issues(page)
        
        # Analyze this post for end customers
        post_leads = analyze_post_for_end_customers(page, post_data)
        all_leads.extend(post_leads)
        
        print(f"    📊 Found {len(post_leads)} leads from this post")
        
        # Delay between posts to avoid rate limiting
        if i < len(posts) - 1:
            delay_time = random.uniform(5, 10)
            print(f"    ⏳ Waiting {delay_time:.1f}s before next post...")
            time.sleep(delay_time)
    
    # Remove duplicates
    if all_leads:
        unique_results = []
        seen_handles = set()
        for result in all_leads:
            handle_key = result['handle'].lower().strip()
            if handle_key not in seen_handles:
                unique_results.append(result)
                seen_handles.add(handle_key)
        
        # Quality and post type breakdown
        quality_counts = {}
        post_type_counts = {}
        for result in unique_results:
            quality = result['lead_quality']
            post_type = result['post_type']
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
            post_type_counts[post_type] = post_type_counts.get(post_type, 0) + 1
        
        print(f"\n📊 REDDIT {NICHE.upper()} CUSTOMER RESULTS:")
        print(f"  🎯 Total unique leads: {len(unique_results)}")
        print(f"  💎 Premium quality: {quality_counts.get('premium', 0)}")
        print(f"  ⭐ Standard quality: {quality_counts.get('standard', 0)}")
        print(f"  📈 Volume quality: {quality_counts.get('volume', 0)}")
        print(f"  🚫 Excluded accounts: {excluded_count}")
        print(f"  🎯 Niche: {NICHE}")
        
        print(f"\n📝 POST TYPE BREAKDOWN:")
        for post_type, count in post_type_counts.items():
            print(f"  📄 {post_type}: {count}")
        
        return unique_results
    else:
        print(f"\n❌ No {NICHE} customers extracted")
        print("💡 This could be due to:")
        print("   • No relevant content found for the search term")
        print("   • Reddit access restrictions")
        print("   • Users in posts/comments are professionals, not customers")
        print("   • Need to adjust search terms or target different subreddits")
        return []

def handle_reddit_access_issues(page):
    """Handle Reddit access issues like login prompts, rate limiting, etc."""
    try:
        page_text = page.inner_text('body').lower()
        page_url = page.url.lower()
        
        # Check for login prompt
        if 'log in' in page_text or 'sign up' in page_text:
            print("    🔐 Login prompt detected, trying to continue without login...")
            
            # Look for "continue" or "skip" buttons
            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Skip")', 
                'a:has-text("Continue")',
                '[data-testid="login-skip"]',
                '.continue-button'
            ]
            
            for selector in continue_selectors:
                try:
                    button = page.query_selector(selector)
                    if button and button.is_visible():
                        print("    🖱️ Clicking continue/skip button")
                        button.click()
                        time.sleep(3)
                        return True
                except:
                    continue
        
        # Check for age verification
        if 'over 18' in page_text or 'nsfw' in page_text:
            print("    🔞 Age verification detected, clicking continue...")
            
            age_selectors = [
                'button:has-text("Yes")',
                'button:has-text("Continue")',
                'button:has-text("I am over 18")',
                '[data-testid="age-verification-continue"]'
            ]
            
            for selector in age_selectors:
                try:
                    button = page.query_selector(selector)
                    if button and button.is_visible():
                        button.click()
                        time.sleep(3)
                        return True
                except:
                    continue
        
        # Check for rate limiting
        if any(term in page_text for term in ['rate limit', 'too many requests', 'slow down']):
            print("    ⏳ Rate limiting detected, waiting longer...")
            time.sleep(random.uniform(15, 30))
            return True
        
        # Check for CAPTCHA
        if 'captcha' in page_text or 'verification' in page_text:
            print("    🤖 CAPTCHA detected - manual intervention may be needed")
            time.sleep(10)  # Give time for manual solving
            return True
        
        return False
        
    except Exception as e:
        print(f"    ⚠️ Error handling access issues: {e}")
        return False

def main():
    """Main Reddit end customer scraper with smart user-aware deduplication"""
    
    estimated_leads = MAX_POSTS_TO_CHECK * 3  # Conservative estimate
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, CURRENT_SEARCH)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    # Update last run time
    update_last_run_time()
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    with sync_playwright() as p:
        print(f"🎯 Launching Reddit {NICHE.upper()} END CUSTOMER scraper...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context
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
            # IMPROVED: Start with Reddit homepage first
            print("🌐 Starting with Reddit homepage...")
            page.goto("https://www.reddit.com", timeout=30000)
            time.sleep(5)
            
            # Handle any access issues
            handle_reddit_access_issues(page)
            
            # Verify Reddit access
            page_title = page.title()
            print(f"📄 Reddit homepage title: {page_title}")
            
            if 'reddit' not in page_title.lower():
                print("⚠️ May not have proper Reddit access")
            
            # Extract niche end customers from Reddit (raw leads)
            raw_leads = extract_reddit_niche_customers(page)
            
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
                seen_handles = set()
                for lead in raw_leads:
                    handle_key = lead.get('handle', '').lower().strip()
                    if handle_key not in seen_handles and len(handle_key) > 1:
                        unique_leads.append(lead)
                        seen_handles.add(handle_key)
                dedup_stats = {"basic": True, "kept": len(unique_leads)}
            
            # Final results summary
            print(f"\n📊 FINAL RESULTS SUMMARY:")
            print(f"  📥 Raw leads extracted: {len(raw_leads)}")
            print(f"  ✅ Unique leads after dedup: {len(unique_leads)}")
            print(f"  📈 Efficiency: {(len(unique_leads) / len(raw_leads) * 100):.1f}% kept")
            print(f"  👤 User: {username}")
            print(f"  🔄 Dedup mode: {DEDUP_MODE}")
            print(f"  📊 Posts processed: {MAX_POSTS_TO_CHECK}")
            print(f"  🎯 Niche: {NICHE}")
            
            if len(unique_leads) > 25:
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
                output_file = f"reddit_{NICHE}_customers_{username}_{timestamp}.csv"
                
                fieldnames = [
                    'name', 'handle', 'bio', 'url', 'platform',
                    'customer_type', 'lead_quality', 'search_source',
                    'post_type', 'transformation_stage', 'niche_goals',
                    'pain_points', 'product_interest', 'support_seeking',
                    'source_type', 'post_title', 'content_preview',
                    'title', 'location', 'followers', 'profile_url',
                    'search_term', 'extraction_method', 'relevance_score',
                    'source_post_url'
                ]
                
                files_saved = []
                
                # Save processed results to main CSV
                if leads:
                    out_path = CSV_DIR / output_file
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(leads)
                    files_saved.append(output_file)
                
                # Save raw results if enabled and different from processed
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    raw_filename = f"reddit_{NICHE}_customers_raw_{username}_{timestamp}.csv"
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
                    
                    print(f"📝 Writing Reddit {NICHE} customers to Google Sheets...")
                    write_leads_to_google_sheet(leads)
                    print(f"✅ Successfully uploaded Reddit {NICHE} customers to Google Sheets")
                    
                    print(f"📤 Sending Reddit {NICHE} leads via email...")
                    send_daily_leads_email()
                    print(f"✅ Reddit {NICHE} customer leads email sent!")
                    
                except ImportError:
                    print("📦 sheets_writer.py or daily_emailer.py not found - export features skipped")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                # Show niche customer samples
                if leads:
                    print(f"\n🎯 {NICHE.upper()} CUSTOMER SAMPLES:")
                    for i, lead in enumerate(leads[:5]):
                        print(f"  {i+1}. {lead['name']} ({lead['lead_quality']} quality)")
                        print(f"     Post Type: {lead['post_type']} | Stage: {lead['transformation_stage']}")
                        print(f"     Goals: {lead['niche_goals']}")
                        print(f"     Source: {lead['source_type']}")
                        print(f"     Post: {lead['post_title'][:50]}...")
                        print(f"     Search: {lead['search_source']}")
                        print()
                
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    print(f"\n📋 Raw leads preserved: {len(raw_leads)} total")
                    
            else:
                print(f"⚠️ No Reddit {NICHE} customers extracted")
                leads = []
                
        except Exception as e:
            print(f"🚨 Reddit scraper error: {e}")
            import traceback
            traceback.print_exc()
            leads = []
        finally:
            print("🔍 Keeping browser open for 5 seconds...")
            time.sleep(5)
            browser.close()
            
        return leads

if __name__ == "__main__":
    print(f"🎯 Reddit {NICHE.upper()} END CUSTOMER Scraper - Smart Deduplication Version")
    print(f"🔍 Target: People who BUY {NICHE} products/services")
    print(f"🚫 Exclude: {NICHE} professionals/coaches")
    print(f"🔍 Search term: '{CURRENT_SEARCH}' {'(from config)' if config.get('search_term') else '(fallback)'}")
    print(f"📍 Target subreddits: {', '.join(END_CUSTOMER_SUBREDDITS[:5])}...")
    print(f"📝 Max posts to check: {MAX_POSTS_TO_CHECK}")
    print(f"💬 Max comments per post: {MAX_COMMENTS_PER_POST}")
    print(f"⏱️ Delay range: {DELAY_MIN}-{DELAY_MAX}s")
    print(f"🛡️ Features:")
    print(f"  • Smart user-aware deduplication")
    print(f"  • Universal niche support")
    print(f"  • Enhanced result tracking")
    print(f"  • Raw lead preservation")
    print(f"  • Config-driven search terms")
    print(f"📱 Reddit-specific features:")
    print(f"  • Post author analysis")
    print(f"  • Comment engagement analysis") 
    print(f"  • Subreddit targeting")
    print(f"  • Help-seeking detection")
    print()
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print(f"🎯 Niche: {NICHE}")
    print()
    
    results = main()
    
    if results and len(results) >= 15:
        print(f"🎉 REDDIT SUCCESS: Reddit {NICHE} customer scraper completed with {len(results)} end customer leads!")
    elif results:
        print(f"✅ Reddit {NICHE} customer scraper completed with {len(results)} leads")
    else:
        print(f"❌ Reddit {NICHE} customer scraper completed with 0 leads")