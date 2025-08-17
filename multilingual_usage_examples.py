#!/usr/bin/env python3
"""
Practical examples of multilingual DM generation
"""

from dm_sequences import generate_dm_with_fallback, generate_multiple_dms
from multilingual_dm_generator import generate_multilingual_batch, detect_user_language
from dm_csv_exporter import export_dms_detailed, batch_export_by_platform

def example_1_auto_language_detection():
    """Example 1: Automatic language detection"""
    
    print("🌍 Example 1: Auto Language Detection")
    print("=" * 45)
    
    # Mixed language contacts (your scraped data)
    contacts = [
        {"name": "Carlos Mendoza", "bio": "Entrenador personal especializado en crossfit y nutrición deportiva"},
        {"name": "Marie Dubois", "bio": "Influenceuse mode et beauté avec 100k followers sur Instagram"},
        {"name": "Hans Mueller", "bio": "Software-Entwickler bei einem KI-Startup in Berlin"},
        {"name": "Giovanni Rossi", "bio": "Chef e food blogger che condivide ricette tradizionali italiane"},
        {"name": "John Smith", "bio": "Tech entrepreneur building AI tools for content creators"},
        {"name": "田中健太", "bio": "ゲーム実況者として活動中、主にRPGをプレイしています"},
        {"name": "김민지", "bio": "뷰티 유튜버로 메이크업 튜토리얼을 제작하고 있습니다"}
    ]
    
    print("🚀 Generating DMs with auto language detection...")
    
    # Your existing function now auto-detects language!
    results = generate_multiple_dms(
        contacts=contacts, 
        platform="instagram",
        auto_detect_language=True  # New parameter
    )
    
    for result in results:
        print(f"\n👤 {result['name']} ({result['language']}):")
        print(f"💬 {result['dm']}")
        print(f"📏 {result['length']} chars")
    
    return results

def example_2_force_specific_language():
    """Example 2: Force specific language for all contacts"""
    
    print("\n🎯 Example 2: Force Specific Language")
    print("=" * 40)
    
    # English-speaking contacts but you want Spanish DMs
    contacts = [
        {"name": "Sarah Johnson", "bio": "Fitness coach and personal trainer"},
        {"name": "Mike Chen", "bio": "Tech YouTuber covering latest gadgets"},
        {"name": "Emma Davis", "bio": "Travel blogger and photographer"}
    ]
    
    print("🚀 Generating Spanish DMs for English-speaking contacts...")
    
    # Force Spanish for all
    spanish_results = generate_multiple_dms(
        contacts=contacts,
        platform="tiktok", 
        language="spanish",  # Force language
        auto_detect_language=False
    )
    
    for result in spanish_results:
        print(f"\n👤 {result['name']} (forced {result['language']}):")
        print(f"💬 {result['dm']}")
    
    return spanish_results

def example_3_multi_platform_multilingual():
    """Example 3: Multi-platform multilingual campaign"""
    
    print("\n📱 Example 3: Multi-Platform Multilingual Campaign")
    print("=" * 55)
    
    # International creator contacts
    international_contacts = [
        {"name": "Alejandra Ruiz", "bio": "Creadora de contenido lifestyle en TikTok desde México"},
        {"name": "Thomas Bernard", "bio": "YouTuber tech français couvrant les startups européennes"},
        {"name": "Yuki Tanaka", "bio": "日本のファッションインフルエンサー、東京を拠点に活動"},
        {"name": "Lisa Weber", "bio": "Deutsche Food-Bloggerin mit Fokus auf vegane Rezepte"}
    ]
    
    platforms = ["tiktok", "youtube", "instagram", "linkedin"]
    
    print("🚀 Generating multilingual campaign across platforms...")
    
    # Generate for each platform with auto-detection
    all_results = {}
    
    for platform in platforms:
        print(f"\n📱 Processing {platform.upper()}...")
        
        results = generate_multiple_dms(
            contacts=international_contacts,
            platform=platform,
            auto_detect_language=True
        )
        
        all_results[platform] = results
        
        # Show first result for each platform
        if results:
            first_result = results[0]
            print(f"   👤 {first_result['name']} ({first_result['language']}):")
            print(f"   💬 {first_result['dm']}")
    
    return all_results

def example_4_language_specific_campaigns():
    """Example 4: Language-specific marketing campaigns"""
    
    print("\n🎯 Example 4: Language-Specific Marketing Campaigns")
    print("=" * 55)
    
    # Same contacts for different language markets
    fitness_contacts = [
        {"name": "Alex Johnson", "bio": "Personal trainer and nutrition coach"},
        {"name": "Maria Santos", "bio": "Fitness influencer and wellness expert"},
        {"name": "David Kim", "bio": "Strength training specialist and gym owner"}
    ]
    
    # Target different language markets
    languages = ["english", "spanish", "french", "german"]
    
    print("🚀 Creating language-specific campaigns...")
    
    campaign_results = {}
    
    for language in languages:
        print(f"\n🌍 {language.upper()} Campaign:")
        print("-" * 25)
        
        results = generate_multiple_dms(
            contacts=fitness_contacts,
            platform="instagram",
            language=language,
            auto_detect_language=False
        )
        
        campaign_results[language] = results
        
        # Show results
        for result in results:
            print(f"👤 {result['name']}:")
            print(f"💬 {result['dm']}")
            print()
    
    return campaign_results

def example_5_csv_export_multilingual():
    """Example 5: CSV export with multilingual data"""
    
    print("\n📊 Example 5: CSV Export with Multilingual Data")
    print("=" * 50)
    
    # Generate multilingual results
    global_contacts = [
        {"name": "Sofia Rodriguez", "bio": "Diseñadora gráfica freelance especializada en branding"},
        {"name": "Antoine Dubois", "bio": "Développeur web passionné par l'intelligence artificielle"},
        {"name": "Marco Bianchi", "bio": "Consulente di marketing digitale per PMI italiane"},
        {"name": "Jessica Chen", "bio": "Content creator focusing on Asian-American lifestyle"}
    ]
    
    print("🚀 Generating multilingual DMs...")
    
    # Generate with auto-detection
    multilingual_results = generate_multiple_dms(
        contacts=global_contacts,
        platform="linkedin",
        auto_detect_language=True
    )
    
    # Export to CSV with language info
    csv_file = export_dms_detailed(
        multilingual_results, 
        "multilingual_campaign.csv"
    )
    
    print(f"✅ Exported multilingual campaign to: {csv_file}")
    
    # Show what was generated
    for result in multilingual_results:
        print(f"\n👤 {result['name']} ({result['language']}):")
        print(f"💬 {result['dm']}")
    
    return csv_file, multilingual_results

def example_6_scraper_integration():
    """Example 6: Integration with your existing scrapers"""
    
    print("\n🔗 Example 6: Scraper Integration with Multilingual")
    print("=" * 55)
    
    def simulate_international_scraper():
        """Simulate scraping international accounts"""
        return [
            # Spanish-speaking users
            {"name": "Ana García", "bio": "Emprendedora digital y consultora en marketing online"},
            {"name": "Diego Morales", "bio": "YouTuber de gaming con más de 500K suscriptores"},
            
            # French-speaking users  
            {"name": "Céline Laurent", "bio": "Photographe professionnelle spécialisée en portraits"},
            {"name": "Maxime Rousseau", "bio": "Créateur de contenu voyage et lifestyle"},
            
            # German-speaking users
            {"name": "Anna Schmidt", "bio": "Fitness-Influencerin aus München mit Fokus auf Yoga"},
            {"name": "Felix Wagner", "bio": "Tech-Blogger der über KI und Automation schreibt"},
        ]
    
    def process_international_campaign():
        """Complete workflow: Scrape → Detect Language → Generate DMs → Export"""
        
        print("🌍 Step 1: Simulating international scraping...")
        contacts = simulate_international_scraper()
        
        print("🧠 Step 2: Generating multilingual DMs...")
        dm_results = generate_multiple_dms(
            contacts=contacts,
            platform="twitter", 
            auto_detect_language=True
        )
        
        print("📊 Step 3: Exporting to CSV...")
        csv_file = export_dms_detailed(dm_results, "international_twitter_campaign.csv")
        
        print("📈 Step 4: Campaign Summary:")
        languages_used = {}
        for result in dm_results:
            lang = result['language']
            languages_used[lang] = languages_used.get(lang, 0) + 1
        
        print(f"   Total DMs: {len(dm_results)}")
        print(f"   Languages: {', '.join(languages_used.keys())}")
        for lang, count in languages_used.items():
            print(f"   {lang.title()}: {count} DMs")
        
        return csv_file, dm_results
    
    # Run the complete workflow
    csv_file, results = process_international_campaign()
    
    print(f"\n✅ International campaign complete!")
    print(f"📄 Results exported to: {csv_file}")
    
    return csv_file, results

def example_7_batch_multilingual_platforms():
    """Example 7: Batch processing across platforms with multilingual"""
    
    print("\n⚡ Example 7: Batch Multilingual Platform Processing")
    print("=" * 60)
    
    # International influencer contacts
    influencer_contacts = [
        {"name": "Isabella Rossi", "bio": "Fashion blogger italiana con focus su sostenibilità"},
        {"name": "Pierre Dubois", "bio": "Chef étoilé partageant ses recettes sur les réseaux"},
        {"name": "Sakura Tanaka", "bio": "美容系YouTuberとして活動、日本のコスメを紹介"},
        {"name": "Carlos Rivera", "bio": "Músico y productor compartiendo su proceso creativo"}
    ]
    
    platforms = ["tiktok", "youtube", "instagram", "linkedin"]
    
    print("🚀 Generating multilingual DMs for all platforms...")
    
    # Use the enhanced batch export with multilingual
    exported_files = {}
    
    for platform in platforms:
        print(f"\n📱 Processing {platform.upper()}...")
        
        # Generate multilingual DMs
        results = generate_multiple_dms(
            contacts=influencer_contacts,
            platform=platform,
            auto_detect_language=True
        )
        
        # Export to CSV
        filename = f"multilingual_{platform}_campaign.csv"
        csv_file = export_dms_detailed(results, filename)
        exported_files[platform] = csv_file
        
        print(f"   ✅ Exported to: {csv_file}")
        
        # Show language distribution
        languages = [r['language'] for r in results]
        unique_languages = set(languages)
        print(f"   🌍 Languages used: {', '.join(unique_languages)}")
    
    print(f"\n🎉 Batch multilingual processing complete!")
    print(f"📁 Files created: {len(exported_files)}")
    
    return exported_files

def run_all_multilingual_examples():
    """Run all multilingual examples"""
    
    print("🌍 MULTILINGUAL DM GENERATION EXAMPLES")
    print("=" * 70)
    
    examples = [
        ("Auto Language Detection", example_1_auto_language_detection),
        ("Force Specific Language", example_2_force_specific_language),
        ("Multi-Platform Multilingual", example_3_multi_platform_multilingual),
        ("Language-Specific Campaigns", example_4_language_specific_campaigns),
        ("CSV Export Multilingual", example_5_csv_export_multilingual),
        ("Scraper Integration", example_6_scraper_integration),
        ("Batch Multilingual Platforms", example_7_batch_multilingual_platforms)
    ]
    
    results = {}
    
    for name, example_func in examples:
        try:
            print(f"\n{'='*70}")
            print(f"🧪 Running: {name}")
            print(f"{'='*70}")
            
            result = example_func()
            results[name] = {"status": "✅ Success", "result": result}
            
        except Exception as e:
            print(f"❌ Error in {name}: {e}")
            results[name] = {"status": "❌ Failed", "error": str(e)}
    
    # Final summary
    print(f"\n{'='*70}")
    print("📊 MULTILINGUAL EXAMPLES SUMMARY")
    print(f"{'='*70}")
    
    successful = 0
    for name, data in results.items():
        print(f"{data['status']} {name}")
        if "Success" in data['status']:
            successful += 1
    
    print(f"\n🎯 Results: {successful}/{len(examples)} examples completed successfully")
    
    print(f"\n🌍 Multilingual Features Available:")
    print("✅ Auto language detection from names and bios")
    print("✅ 12+ supported languages (Spanish, French, German, etc.)")
    print("✅ Platform-specific cultural adaptations")
    print("✅ CSV export with language metadata")
    print("✅ Batch processing across platforms")
    print("✅ Integration with existing persona system")
    
    return results

if __name__ == "__main__":
    run_all_multilingual_examples()