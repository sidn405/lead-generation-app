# deduplication_config.py
"""
Configuration options for lead deduplication strategies
"""

from enum import Enum
from typing import Dict, Any

class DeduplicationMode(Enum):
    """Different deduplication strategies"""
    KEEP_ALL = "keep_all"  # No deduplication - keep every lead
    SESSION_ONLY = "session_only"  # Remove duplicates only within current scrape
    SMART_USER_AWARE = "smart_user_aware"  # Smart dedup across user's history (recommended)
    AGGRESSIVE = "aggressive"  # Old method - remove by name similarity

# Default configuration
DEFAULT_DEDUP_CONFIG = {
    "mode": DeduplicationMode.SMART_USER_AWARE,
    "preserve_raw_leads": True,  # Always save raw leads to CSV
    "min_name_length": 2,
    "exclude_generic_names": True,
    "cross_platform_dedup": False,  # Whether to check duplicates across platforms
}

def get_deduplication_config(platform: str = "facebook") -> Dict[str, Any]:
    """
    Get deduplication configuration for a platform
    
    Args:
        platform: Platform name (facebook, twitter, etc.)
        
    Returns:
        Dictionary with deduplication settings
    """
    config = DEFAULT_DEDUP_CONFIG.copy()
    
    # Platform-specific overrides
    platform_configs = {
        "facebook": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "twitter": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "instagram": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "tiktok": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "youtube": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "medium": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "reddit": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
        },
        "linkedin": {
            "mode": DeduplicationMode.SMART_USER_AWARE,
            "preserve_raw_leads": True,
            "cross_platform_dedup": True,  # LinkedIn profiles are more unique
        }
    }
    
    if platform in platform_configs:
        config.update(platform_configs[platform])
    
    return config

def explain_deduplication_modes():
    """Print explanation of different deduplication modes"""
    explanations = {
        DeduplicationMode.KEEP_ALL: {
            "description": "Keep every single lead found",
            "pros": ["Maximum leads", "No false removals"],
            "cons": ["May include true duplicates", "Larger files"],
            "best_for": "Testing, first-time users, maximum coverage"
        },
        DeduplicationMode.SESSION_ONLY: {
            "description": "Remove duplicates only within current scrape",
            "pros": ["Clean current results", "Fast processing"],
            "cons": ["Duplicates across scrapes", "No historical awareness"],
            "best_for": "Single-session testing, isolated scrapes"
        },
        DeduplicationMode.SMART_USER_AWARE: {
            "description": "Intelligent dedup based on multiple factors, user-specific history",
            "pros": ["Maximum unique leads", "User-specific", "Preserves different people with same names"],
            "cons": ["More complex", "Requires storage"],
            "best_for": "Production use, multiple users, ongoing campaigns"
        },
        DeduplicationMode.AGGRESSIVE: {
            "description": "Remove leads with similar names (old method)",
            "pros": ["Simple", "Fast"],
            "cons": ["Removes many valid leads", "Too restrictive"],
            "best_for": "Legacy compatibility only (not recommended)"
        }
    }
    
    print("🔍 Lead Deduplication Mode Comparison:\n")
    for mode, info in explanations.items():
        print(f"📋 {mode.value.upper()}:")
        print(f"   Description: {info['description']}")
        print(f"   ✅ Pros: {', '.join(info['pros'])}")
        print(f"   ❌ Cons: {', '.join(info['cons'])}")
        print(f"   🎯 Best for: {info['best_for']}")
        print()

# Usage examples
def apply_deduplication_strategy(raw_leads, username, platform, mode=None):
    """
    Apply the specified deduplication strategy
    
    Args:
        raw_leads: List of lead dictionaries
        username: Username for user-specific dedup
        platform: Platform name
        mode: DeduplicationMode enum or None for default
        
    Returns:
        Tuple of (unique_leads, raw_leads, stats)
    """
    from smart_duplicate_handler import SmartDuplicateHandler
    
    if mode is None:
        config = get_deduplication_config(platform)
        mode = config["mode"]
    
    if mode == DeduplicationMode.KEEP_ALL:
        print("📋 Mode: KEEP ALL - No deduplication")
        return raw_leads, raw_leads, {"mode": "keep_all", "kept": len(raw_leads)}
        
    elif mode == DeduplicationMode.SESSION_ONLY:
        print("📋 Mode: SESSION ONLY - Current scrape dedup")
        handler = SmartDuplicateHandler(username, platform)
        unique_leads, stats = handler.remove_duplicates(raw_leads, current_session_only=True)
        return unique_leads, raw_leads, stats
        
    elif mode == DeduplicationMode.SMART_USER_AWARE:
        print("📋 Mode: SMART USER AWARE - Intelligent deduplication")
        from smart_duplicate_handler import process_leads_with_smart_deduplication
        unique_leads, stats = process_leads_with_smart_deduplication(
            raw_leads, username, platform
        )
        return unique_leads, raw_leads, stats
        
    elif mode == DeduplicationMode.AGGRESSIVE:
        print("📋 Mode: AGGRESSIVE - Name-based removal (not recommended)")
        unique_leads = []
        seen_names = set()
        for lead in raw_leads:
            name_key = lead.get('name', '').lower().strip()
            if name_key not in seen_names and len(name_key) > 1:
                unique_leads.append(lead)
                seen_names.add(name_key)
        
        stats = {
            "mode": "aggressive",
            "raw_leads": len(raw_leads),
            "unique_leads": len(unique_leads),
            "removed": len(raw_leads) - len(unique_leads)
        }
        return unique_leads, raw_leads, stats
    
    else:
        raise ValueError(f"Unknown deduplication mode: {mode}")

if __name__ == "__main__":
    # Show mode explanations
    explain_deduplication_modes()
    
    # Show current config
    config = get_deduplication_config("facebook")
    print(f"Current Facebook config: {config}")