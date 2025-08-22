
"""
CSV Export Functions for DM Generation System
Works with your existing dm_sequences.py
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

def export_dms_to_csv(dm_results: List[Dict], filename: str = None, include_metadata: bool = True) -> str:
    """
    Export DM generation results to CSV
    
    Args:
        dm_results: List of dicts from generate_multiple_dms()
        filename: Optional filename (auto-generated if None)
        include_metadata: Include extra columns like persona, platform, length
    
    Returns:
        str: Path to exported CSV file
    """
    
    if not dm_results:
        raise ValueError("No DM results to export")
    
    # Auto-generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        platform = dm_results[0].get('platform', 'mixed') if dm_results else 'unknown'
        filename = f"dm_export_{platform}_{timestamp}.csv"
    
    # Ensure .csv extension
    if not filename.endswith('.csv'):
        filename += '.csv'
    
    # Define columns based on include_metadata flag
    if include_metadata:
        columns = [
            'name', 'bio', 'dm', 'persona', 'platform', 
            'length', 'timestamp', 'has_error', 'error_message'
        ]
    else:
        columns = ['name', 'bio', 'dm']
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        
        # Write header
        writer.writeheader()
        
        # Write data rows
        for result in dm_results:
            row = {}
            
            # Basic columns
            row['name'] = result.get('name', '')
            row['bio'] = result.get('bio', '')
            row['dm'] = result.get('dm', '')
            
            # Metadata columns (if requested)
            if include_metadata:
                row['persona'] = result.get('persona', '')
                row['platform'] = result.get('platform', '')
                row['length'] = result.get('length', len(result.get('dm', '')))
                row['timestamp'] = datetime.now().isoformat()
                row['has_error'] = 'Yes' if 'error' in result else 'No'
                row['error_message'] = result.get('error', '')
            
            writer.writerow(row)
    
    print(f"✅ Exported {len(dm_results)} DMs to {filename}")
    return filename

def export_dms_simple(dm_results: List[Dict], filename: str = None) -> str:
    """
    Simple CSV export with just name, bio, and DM
    Perfect for importing into other tools
    """
    return export_dms_to_csv(dm_results, filename, include_metadata=False)

def export_dms_detailed(dm_results: List[Dict], filename: str = None) -> str:
    """
    Detailed CSV export with all metadata
    Great for analysis and tracking
    """
    return export_dms_to_csv(dm_results, filename, include_metadata=True)

def import_contacts_from_csv(filename: str, name_column: str = 'name', bio_column: str = 'bio') -> List[Dict]:
    """
    Import contacts from CSV for DM generation
    
    Args:
        filename: Path to CSV file
        name_column: Name of the column containing names
        bio_column: Name of the column containing bios
    
    Returns:
        List of contact dicts ready for generate_multiple_dms()
    """
    
    contacts = []
    
    with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            if name_column in row and bio_column in row:
                contacts.append({
                    'name': row[name_column].strip(),
                    'bio': row[bio_column].strip()
                })
            else:
                print(f"⚠️ Missing columns in row: {row}")
    
    print(f"✅ Imported {len(contacts)} contacts from {filename}")
    return contacts

def batch_export_by_platform(contacts: List[Dict], platforms: List[str], output_dir: str = "dm_exports") -> Dict[str, str]:
    """
    Generate DMs for multiple platforms and export each to separate CSV
    
    Args:
        contacts: List of contact dicts
        platforms: List of platform names
        output_dir: Directory to save CSV files
    
    Returns:
        Dict mapping platform to CSV filename
    """
    
    # Import here to avoid circular imports
    try:
        from dm_sequences import generate_multiple_dms
    except ImportError:
        raise ImportError("Could not import generate_multiple_dms. Make sure dm_sequences.py is available.")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    exported_files = {}
    
    for platform in platforms:
        print(f"\n🚀 Generating DMs for {platform}...")
        
        # Generate DMs for this platform
        dm_results = generate_multiple_dms(contacts, platform)
        
        # Export to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"dms_{platform}_{timestamp}.csv")
        
        export_path = export_dms_detailed(dm_results, filename)
        exported_files[platform] = export_path
        
        print(f"✅ {platform} DMs exported to {export_path}")
    
    return exported_files

def create_campaign_summary(dm_results: List[Dict], filename: str = None) -> str:
    """
    Create a summary CSV with campaign statistics
    """
    
    if not dm_results:
        return "No data to summarize"
    
    # Calculate statistics
    stats = {
        'total_dms': len(dm_results),
        'successful_dms': len([r for r in dm_results if 'error' not in r]),
        'failed_dms': len([r for r in dm_results if 'error' in r]),
        'platform': dm_results[0].get('platform', 'unknown'),
        'avg_length': sum(r.get('length', 0) for r in dm_results) / len(dm_results),
        'personas_used': len(set(r.get('persona', '') for r in dm_results)),
        'timestamp': datetime.now().isoformat()
    }
    
    # Count personas
    persona_counts = {}
    for result in dm_results:
        persona = result.get('persona', 'unknown')
        persona_counts[persona] = persona_counts.get(persona, 0) + 1
    
    # Auto-generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        platform = stats['platform']
        filename = f"campaign_summary_{platform}_{timestamp}.csv"
    
    # Write summary CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Campaign overview
        writer.writerow(['Campaign Summary'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total DMs Generated', stats['total_dms']])
        writer.writerow(['Successful DMs', stats['successful_dms']])
        writer.writerow(['Failed DMs', stats['failed_dms']])
        writer.writerow(['Platform', stats['platform']])
        writer.writerow(['Average Length', f"{stats['avg_length']:.1f} chars"])
        writer.writerow(['Personas Used', stats['personas_used']])
        writer.writerow(['Generated At', stats['timestamp']])
        
        writer.writerow([])  # Empty row
        
        # Persona breakdown
        writer.writerow(['Persona Breakdown'])
        writer.writerow(['Persona', 'Count', 'Percentage'])
        for persona, count in persona_counts.items():
            percentage = (count / stats['total_dms']) * 100
            writer.writerow([persona, count, f"{percentage:.1f}%"])
    
    print(f"✅ Campaign summary exported to {filename}")
    return filename

# Convenience function for quick export
def quick_export(contacts: List[Dict], platform: str = "twitter", export_type: str = "detailed") -> str:
    """
    Quick one-liner to generate DMs and export to CSV
    
    Args:
        contacts: List of contact dicts  
        platform: Platform to generate for
        export_type: 'simple' or 'detailed'
    
    Returns:
        Path to exported CSV file
    """
    
    # Import here to avoid circular imports
    try:
        from dm_sequences import generate_multiple_dms
    except ImportError:
        raise ImportError("Could not import generate_multiple_dms. Make sure dm_sequences.py is available.")
    
    print(f"🚀 Quick export for {len(contacts)} contacts on {platform}...")
    
    # Generate DMs
    dm_results = generate_multiple_dms(contacts, platform)
    
    # Export based on type
    if export_type == "simple":
        return export_dms_simple(dm_results)
    else:
        return export_dms_detailed(dm_results)

# Test function
def test_csv_export():
    """Test CSV export functionality"""
    
    print("🧪 Testing CSV Export Functions")
    print("=" * 40)
    
    # Sample data for testing
    test_results = [
        {
            'name': 'John Smith',
            'bio': 'Software engineer passionate about AI',
            'dm': 'Hey John! Love what you\'re doing with tech. Let\'s connect! 🚀',
            'persona': 'tech',
            'platform': 'twitter',
            'length': 63
        },
        {
            'name': 'Sarah Johnson',
            'bio': 'Fitness coach helping people achieve goals',
            'dm': 'Hi Sarah! Your fitness content is amazing! Would love to chat sometime 💬',
            'persona': 'fitness',
            'platform': 'twitter',
            'length': 73
        },
        {
            'name': 'Mike Chen',
            'bio': 'Crypto trader and blockchain enthusiast',
            'dm': 'Hey Mike! Fellow crypto enthusiast here - let\'s connect! ✨',
            'persona': 'crypto',
            'platform': 'twitter',
            'length': 56,
            'error': 'API rate limit exceeded'
        }
    ]
    
    # Test simple export
    simple_file = export_dms_simple(test_results, "test_simple.csv")
    print(f"✅ Simple export: {simple_file}")
    
    # Test detailed export
    detailed_file = export_dms_detailed(test_results, "test_detailed.csv")
    print(f"✅ Detailed export: {detailed_file}")
    
    # Test campaign summary
    summary_file = create_campaign_summary(test_results, "test_summary.csv")
    print(f"✅ Campaign summary: {summary_file}")
    
    print(f"\n📊 Files created:")
    for file in [simple_file, detailed_file, summary_file]:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"  • {file} ({size} bytes)")

if __name__ == "__main__":
    test_csv_export()