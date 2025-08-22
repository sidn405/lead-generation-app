
import hashlib
import json
import os
from datetime import datetime
from typing import List, Dict, Set, Tuple

class SmartDuplicateHandler:
    """
    User-aware duplicate detection that preserves raw leads and only removes
    TRUE duplicates (same person), not just people with similar names.
    """
    
    def __init__(self, username: str, platform: str):
        self.username = username
        self.platform = platform
        self.user_leads_file = f"user_leads_{username}_{platform}.json"
        self.historical_leads = self._load_historical_leads()
    
    def _load_historical_leads(self) -> Dict:
        """Load user's historical leads for duplicate checking"""
        try:
            if os.path.exists(self.user_leads_file):
                with open(self.user_leads_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"leads": [], "lead_hashes": set()}
        except Exception as e:
            print(f"⚠️ Error loading historical leads: {e}")
            return {"leads": [], "lead_hashes": set()}
    
    def _save_historical_leads(self):
        """Save updated historical leads"""
        try:
            # Convert set to list for JSON serialization
            data_to_save = {
                "leads": self.historical_leads["leads"],
                "lead_hashes": list(self.historical_leads["lead_hashes"]),
                "last_updated": datetime.now().isoformat()
            }
            with open(self.user_leads_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Error saving historical leads: {e}")
    
    def _create_lead_hash(self, lead: Dict) -> str:
        """
        Create a unique hash for a lead based on multiple factors.
        This helps identify the SAME PERSON, not just people with similar names.
        """
        # Use multiple identifying factors
        identifying_factors = []
        
        # Name (normalized)
        name = lead.get('name', '').lower().strip()
        if name:
            identifying_factors.append(f"name:{name}")
        
        # Profile URL (most unique identifier)
        profile_url = lead.get('profile_url', '') or lead.get('url', '')
        if profile_url and profile_url != 'URL not found':
            # Extract the unique part of Facebook URLs
            if 'facebook.com' in profile_url:
                # Extract profile ID or username from URL
                url_identifier = profile_url.split('facebook.com/')[-1].split('?')[0]
                identifying_factors.append(f"url:{url_identifier}")
        
        # Handle (if different from name)
        handle = lead.get('handle', '').lower().strip()
        if handle and handle != name:
            identifying_factors.append(f"handle:{handle}")
        
        # Bio keywords (for additional context)
        bio = lead.get('bio', '').lower()[:100]  # First 100 chars for context
        if bio and bio != f"facebook user interested in":  # Skip generic bios
            identifying_factors.append(f"bio_start:{bio}")
        
        # Create hash from all factors
        if identifying_factors:
            hash_string = '|'.join(sorted(identifying_factors))
            return hashlib.md5(hash_string.encode()).hexdigest()
        
        # Fallback: just use name if nothing else available
        return hashlib.md5(name.encode()).hexdigest() if name else ""
    
    def remove_duplicates(self, raw_leads: List[Dict], 
                         current_session_only: bool = False) -> Tuple[List[Dict], Dict]:
        """
        Smart duplicate removal that preserves maximum leads while removing true duplicates.
        
        Args:
            raw_leads: List of lead dictionaries
            current_session_only: If True, only check for duplicates within current scrape
                                 If False, check against user's historical leads too
        
        Returns:
            Tuple of (unique_leads, stats)
        """
        print(f"🔍 Smart duplicate detection for {self.username} on {self.platform}")
        print(f"📊 Processing {len(raw_leads)} raw leads...")
        
        if current_session_only:
            print("📋 Mode: Current session only (ignoring historical leads)")
        else:
            print(f"📋 Mode: Cross-session (checking against {len(self.historical_leads.get('lead_hashes', []))} historical leads)")
        
        unique_leads = []
        session_hashes = set()
        stats = {
            'raw_leads': len(raw_leads),
            'current_session_duplicates': 0,
            'historical_duplicates': 0,
            'unique_leads': 0,
            'same_name_different_person': 0,
            'invalid_leads': 0
        }
        
        # Convert historical hashes to set if needed
        if isinstance(self.historical_leads.get("lead_hashes", []), list):
            self.historical_leads["lead_hashes"] = set(self.historical_leads["lead_hashes"])
        
        for i, lead in enumerate(raw_leads):
            try:
                # Basic validation
                name = lead.get('name', '').strip()
                if not name or len(name) < 2:
                    stats['invalid_leads'] += 1
                    continue
                
                # Create unique hash for this lead
                lead_hash = self._create_lead_hash(lead)
                if not lead_hash:
                    stats['invalid_leads'] += 1
                    continue
                
                # Check for duplicates in current session
                if lead_hash in session_hashes:
                    stats['current_session_duplicates'] += 1
                    print(f"  📎 Current session duplicate: {name}")
                    continue
                
                # Check for duplicates in historical data (if enabled)
                if not current_session_only and lead_hash in self.historical_leads.get("lead_hashes", set()):
                    stats['historical_duplicates'] += 1
                    print(f"  📚 Historical duplicate: {name}")
                    continue
                
                # Check if this is a "same name, different person" case
                same_name_count = sum(1 for existing_lead in unique_leads 
                                    if existing_lead.get('name', '').lower().strip() == name.lower())
                if same_name_count > 0:
                    stats['same_name_different_person'] += 1
                    print(f"  👥 Same name, different person: {name} (#{same_name_count + 1})")
                
                # This is a unique lead!
                unique_leads.append(lead)
                session_hashes.add(lead_hash)
                stats['unique_leads'] += 1
                
                # Progress update
                if (i + 1) % 50 == 0:
                    print(f"    Progress: {i + 1}/{len(raw_leads)} processed, {len(unique_leads)} unique so far")
            
            except Exception as e:
                print(f"  ⚠️ Error processing lead {i}: {e}")
                stats['invalid_leads'] += 1
                continue
        
        # Update historical leads with new unique leads (if not current_session_only)
        if not current_session_only:
            print("💾 Updating historical leads database...")
            for lead in unique_leads:
                lead_hash = self._create_lead_hash(lead)
                if lead_hash:
                    self.historical_leads["lead_hashes"].add(lead_hash)
                    
                    # Also store a simplified version of the lead for reference
                    simplified_lead = {
                        'name': lead.get('name'),
                        'profile_url': lead.get('profile_url', lead.get('url')),
                        'platform': self.platform,
                        'date_added': datetime.now().isoformat(),
                        'search_term': lead.get('search_term', ''),
                        'hash': lead_hash
                    }
                    self.historical_leads["leads"].append(simplified_lead)
            
            self._save_historical_leads()
        
        # Print comprehensive stats
        print(f"\n📊 Duplicate Detection Results:")
        print(f"  📥 Raw leads: {stats['raw_leads']}")
        print(f"  ✅ Unique leads: {stats['unique_leads']}")
        print(f"  📎 Current session dupes: {stats['current_session_duplicates']}")
        if not current_session_only:
            print(f"  📚 Historical dupes: {stats['historical_duplicates']}")
        print(f"  👥 Same name, diff person: {stats['same_name_different_person']}")
        print(f"  ❌ Invalid leads: {stats['invalid_leads']}")
        print(f"  📈 Efficiency: {(stats['unique_leads'] / stats['raw_leads'] * 100):.1f}% kept")
        
        return unique_leads, stats
    
    def get_user_lead_count(self) -> int:
        """Get total number of leads for this user"""
        return len(self.historical_leads.get("leads", []))
    
    def clear_user_history(self):
        """Clear historical leads for this user (admin function)"""
        self.historical_leads = {"leads": [], "lead_hashes": set()}
        if os.path.exists(self.user_leads_file):
            os.remove(self.user_leads_file)
        print(f"🗑️ Cleared lead history for {self.username}")

# Integration function for the Facebook scraper
def process_leads_with_smart_deduplication(raw_leads: List[Dict], 
                                         username: str, 
                                         platform: str = "facebook",
                                         keep_all_raw: bool = False) -> Tuple[List[Dict], List[Dict]]:
    """
    Process leads with smart deduplication.
    
    Args:
        raw_leads: List of raw lead dictionaries
        username: Username for user-specific deduplication
        platform: Platform name
        keep_all_raw: If True, also return raw leads alongside unique leads
    
    Returns:
        Tuple of (unique_leads, raw_leads) if keep_all_raw=True
        Otherwise just unique_leads
    """
    handler = SmartDuplicateHandler(username, platform)
    
    # Use cross-session deduplication by default
    unique_leads, stats = handler.remove_duplicates(raw_leads, current_session_only=False)
    
    if keep_all_raw:
        return unique_leads, raw_leads
    else:
        return unique_leads, stats

# Example usage in Facebook scraper:
def integrate_with_facebook_scraper():
    """
    Example of how to integrate this with the Facebook scraper
    """
    # In your extract_facebook_profiles function, replace the old duplicate removal:
    
    # OLD CODE (remove this):
    # if results:
    #     unique_results = []
    #     seen_names = set()
    #     for result in results:
    #         name_key = result['name'].lower().strip()
    #         if name_key not in seen_names and len(name_key) > 1:
    #             unique_results.append(result)
    #             seen_names.add(name_key)
    
    # NEW CODE (use this instead):
    # if results:
    #     from smart_duplicate_handler import process_leads_with_smart_deduplication
    #     unique_results, stats = process_leads_with_smart_deduplication(
    #         raw_leads=results,
    #         username=username,  # Pass the username from setup_scraper_with_limits
    #         platform="facebook"
    #     )
    pass

if __name__ == "__main__":
    # Test the duplicate handler
    test_leads = [
        {"name": "John Smith", "profile_url": "https://facebook.com/john.smith.123", "bio": "Love cooking"},
        {"name": "John Smith", "profile_url": "https://facebook.com/john.smith.456", "bio": "Software engineer"},
        {"name": "John Smith", "profile_url": "https://facebook.com/john.smith.123", "bio": "Love cooking"},  # True duplicate
        {"name": "Jane Doe", "profile_url": "URL not found", "bio": "Facebook user interested in pastry chef"},
        {"name": "Jane Doe", "profile_url": "https://facebook.com/jane.doe.real", "bio": "Professional baker"},
    ]
    
    handler = SmartDuplicateHandler("test_user", "facebook")
    unique_leads, stats = handler.remove_duplicates(test_leads)
    
    print(f"\nTest Results: {len(unique_leads)} unique leads from {len(test_leads)} raw leads")