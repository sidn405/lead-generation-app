import pandas as pd
import os
import re
from datetime import datetime
import glob
from collections import defaultdict
import json
import hashlib

class OrganizedLeadAnalyzer:
    def __init__(self):
        self.platforms = ['facebook', 'instagram', 'twitter', 'linkedin', 'youtube', 'tiktok', 'medium', 'reddit']
        self.all_leads = []
        self.platform_stats = defaultdict(int)
        self.niche_stats = defaultdict(int)
        self.business_type_stats = defaultdict(int)
        self.platform_niche_stats = defaultdict(lambda: defaultdict(int))
        self.file_stats = {}
        self.duplicate_stats = defaultdict(lambda: {'total_duplicates': 0, 'unique_leads': 0, 'duplicate_groups': 0})
        
        # Define niche keywords for categorization
        self.niche_keywords = {
            'fitness_coaching': [
                'fitness coach', 'personal trainer', 'fitness trainer', 'workout coach', 
                'gym trainer', 'fitness instructor', 'strength coach', 'bodybuilding coach'
            ],
            'weight_loss': [
                'weight loss', 'lose weight', 'fat loss', 'weight management', 'diet coach',
                'weight loss coach', 'slimming', 'body transformation', 'weight watchers'
            ],
            'wellness_health': [
                'wellness coach', 'health coach', 'holistic health', 'nutrition coach',
                'nutritionist', 'dietitian', 'healthy living', 'wellness expert', 'health guru'
            ],
            'mom_fitness': [
                'mom fitness', 'mama fitness', 'mother fitness', 'postpartum fitness',
                'pregnancy fitness', 'mom workout', 'busy mom', 'mom health', 'mommy fitness'
            ],
            'business_coaching': [
                'business coach', 'entrepreneur coach', 'startup coach', 'business mentor',
                'business consultant', 'executive coach', 'leadership coach', 'success coach'
            ],
            'financial_investment': [
                'financial advisor', 'investment advisor', 'stock investor', 'crypto investor',
                'trading coach', 'wealth coach', 'financial planner', 'investment coach'
            ],
            'life_coaching': [
                'life coach', 'mindset coach', 'motivation coach', 'confidence coach',
                'self help', 'personal development', 'transformation coach', 'mindfulness coach'
            ],
            'content_creator': [
                'influencer', 'content creator', 'social media', 'youtuber', 'blogger',
                'tiktoker', 'instagram model', 'online personality', 'digital creator'
            ]
        }
        
        # Business targeting classification
        self.business_indicators = {
            'target_business': {
                'service_providers': [
                    'coach', 'trainer', 'consultant', 'advisor', 'instructor', 'mentor',
                    'therapist', 'specialist', 'expert', 'guru', 'professional'
                ],
                'business_titles': [
                    'ceo', 'founder', 'owner', 'director', 'manager', 'entrepreneur',
                    'business owner', 'agency owner', 'studio owner', 'gym owner'
                ],
                'service_verbs': [
                    'help', 'teach', 'train', 'guide', 'mentor', 'coach', 'consult',
                    'advise', 'specialize in', 'expert in', 'offering', 'providing'
                ],
                'business_context': [
                    'clients', 'students', 'members', 'community', 'program', 'course',
                    'service', 'consultation', 'sessions', 'packages', 'business'
                ]
            },
            'end_customer': {
                'personal_goals': [
                    'want to', 'trying to', 'looking to', 'need to', 'goal is',
                    'working on', 'struggling with', 'hoping to', 'planning to'
                ],
                'customer_language': [
                    'looking for help', 'need advice', 'seeking guidance', 'want results',
                    'need motivation', 'looking for trainer', 'searching for coach'
                ],
                'personal_journey': [
                    'my journey', 'my transformation', 'my goal', 'my fitness',
                    'my weight loss', 'started my', 'beginning my'
                ]
            }
        }
    
    def create_duplicate_key(self, lead_data):
        """Create a unique key for duplicate detection based on name + email"""
        # Get name field (try multiple possible column names)
        name_fields = ['name', 'full_name', 'username', 'handle', 'display_name', 'first_name']
        email_fields = ['email', 'email_address', 'contact_email']
        
        name = ""
        email = ""
        
        # Find name
        for field in name_fields:
            if field in lead_data and pd.notna(lead_data[field]) and str(lead_data[field]).strip():
                name = str(lead_data[field]).strip().lower()
                break
        
        # Find email  
        for field in email_fields:
            if field in lead_data and pd.notna(lead_data[field]) and str(lead_data[field]).strip():
                email = str(lead_data[field]).strip().lower()
                break
        
        # Only create key if both name and email exist
        if name and email and name != 'nan' and email != 'nan':
            return f"{name}|{email}"
        
        return None
    
    def find_duplicates_in_dataframe(self, df):
        """Find duplicates in a single dataframe"""
        duplicate_groups = defaultdict(list)
        valid_leads = []
        
        for idx, row in df.iterrows():
            lead_data = row.to_dict()
            dup_key = self.create_duplicate_key(lead_data)
            
            if dup_key:
                duplicate_groups[dup_key].append({
                    'index': idx,
                    'data': lead_data
                })
            else:
                # Keep leads without name+email combo (incomplete data)
                valid_leads.append(lead_data)
        
        # Separate duplicates and uniques
        duplicates = []
        unique_leads = []
        
        for dup_key, group in duplicate_groups.items():
            if len(group) > 1:
                # Multiple entries with same name+email = duplicates
                # Keep first occurrence, mark others as duplicates
                unique_leads.append(group[0]['data'])
                
                for duplicate in group[1:]:
                    duplicate_entry = duplicate['data'].copy()
                    duplicate_entry['duplicate_reason'] = f"Duplicate of: {dup_key.split('|')[0]} ({dup_key.split('|')[1]})"
                    duplicate_entry['original_index'] = group[0]['index']
                    duplicate_entry['duplicate_index'] = duplicate['index']
                    duplicates.append(duplicate_entry)
            else:
                # Single entry = unique
                unique_leads.append(group[0]['data'])
        
        # Add back leads without complete name+email data
        unique_leads.extend(valid_leads)
        
        return unique_leads, duplicates
    
    def analyze_file_with_duplicates(self, filepath):
        """Analyze file and handle duplicates"""
        try:
            print(f"\n🔍 Analyzing with duplicate detection: {filepath}")
            
            df = pd.read_csv(filepath)
            original_count = len(df)
            platform = self.identify_platform(filepath)
            
            # Find and separate duplicates
            unique_leads, duplicates = self.find_duplicates_in_dataframe(df)
            
            # Create clean dataframe
            clean_df = pd.DataFrame(unique_leads)
            duplicates_df = pd.DataFrame(duplicates) if duplicates else pd.DataFrame()
            
            # Export duplicates if found
            if len(duplicates) > 0:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                base_name = os.path.splitext(os.path.basename(filepath))[0]
                duplicate_filename = f"{base_name}_DUPLICATES_{timestamp}.csv"
                duplicates_df.to_csv(duplicate_filename, index=False)
                print(f"  📁 Exported {len(duplicates)} duplicates to: {duplicate_filename}")
            
            # Update duplicate stats
            duplicate_groups = defaultdict(int)
            for dup in duplicates:
                key = dup.get('duplicate_reason', 'unknown')
                duplicate_groups[key] += 1
            
            self.duplicate_stats[filepath] = {
                'total_duplicates': len(duplicates),
                'unique_leads': len(unique_leads),
                'duplicate_groups': len(duplicate_groups),
                'original_count': original_count,
                'duplicate_file': duplicate_filename if duplicates else None
            }
            
            # Continue with normal analysis using clean data
            filename_lower = filepath.lower()
            is_end_customer_file = any(keyword in filename_lower for keyword in ['fitness_customers', 'end_customer', '_ec_', '_customers'])
            
            # Categorize leads
            niche_counts = defaultdict(int)
            business_target_counts = defaultdict(int)
            
            for lead in unique_leads:
                # Niche categorization
                niche = self.categorize_niche(lead)
                niche_counts[niche] += 1
                self.niche_stats[niche] += 1
                self.platform_niche_stats[platform][niche] += 1
                
                # NUCLEAR business targeting classification
                if is_end_customer_file:
                    business_target = 'end_customer'
                else:
                    business_target = self.nuclear_classify(lead, filepath)
                
                business_target_counts[business_target] += 1
                self.business_type_stats[business_target] += 1
            
            # Store file stats
            file_size = os.path.getsize(filepath)
            modified_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            stats = {
                'filename': filepath,
                'platform': platform,
                'total_leads': len(unique_leads),
                'original_leads': original_count,
                'duplicates_removed': len(duplicates),
                'file_size': file_size,
                'modified': modified_time,
                'columns': list(df.columns),
                'niche_breakdown': dict(niche_counts),
                'business_target_breakdown': dict(business_target_counts),
                'is_end_customer_file': is_end_customer_file,
                'duplicate_stats': self.duplicate_stats[filepath]
            }
            
            self.platform_stats[platform] += len(unique_leads)
            self.file_stats[filepath] = stats
            self.all_leads.extend(unique_leads)
            
            # Calculate percentages
            end_customers = business_target_counts.get('end_customer', 0)
            target_businesses = business_target_counts.get('target_business', 0)
            
            print(f"  ✅ Platform: {platform.replace('_end_customers', '').title()}")
            print(f"  📊 Original: {original_count} | Clean: {len(unique_leads)} | Duplicates: {len(duplicates)}")
            print(f"  🎯 End Customers: {end_customers} | Businesses: {target_businesses}")
            
            return stats
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def analyze_file(self, filepath):
        """Legacy method - now uses duplicate detection"""
        return self.analyze_file_with_duplicates(filepath)
    
    def analyze_single_file_for_duplicates(self, filepath):
        """Standalone duplicate analysis for a single file"""
        try:
            print(f"\n🔍 DUPLICATE ANALYSIS: {filepath}")
            print("=" * 60)
            
            if not os.path.exists(filepath):
                print(f"❌ File not found: {filepath}")
                return None
            
            df = pd.read_csv(filepath)
            original_count = len(df)
            
            # Find duplicates
            unique_leads, duplicates = self.find_duplicates_in_dataframe(df)
            
            # Generate report
            print(f"📋 RESULTS:")
            print(f"  Original leads: {original_count:,}")
            print(f"  Unique leads: {len(unique_leads):,}")
            print(f"  Duplicates found: {len(duplicates):,}")
            print(f"  Duplicate rate: {(len(duplicates)/original_count)*100:.1f}%")
            
            if duplicates:
                # Show duplicate examples
                print(f"\n🔍 DUPLICATE EXAMPLES:")
                duplicate_groups = defaultdict(list)
                for dup in duplicates[:10]:  # Show first 10
                    reason = dup.get('duplicate_reason', 'Unknown')
                    duplicate_groups[reason].append(dup)
                
                for reason, group in list(duplicate_groups.items())[:5]:
                    print(f"  • {reason} ({len(group)} duplicates)")
                
                # Export files
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                base_name = os.path.splitext(os.path.basename(filepath))[0]
                
                # Export duplicates
                duplicate_filename = f"{base_name}_DUPLICATES_{timestamp}.csv"
                duplicates_df = pd.DataFrame(duplicates)
                duplicates_df.to_csv(duplicate_filename, index=False)
                print(f"\n📁 EXPORTED:")
                print(f"  Duplicates: {duplicate_filename}")
                
                # Export clean file
                clean_filename = f"{base_name}_CLEAN_{timestamp}.csv"
                clean_df = pd.DataFrame(unique_leads)
                clean_df.to_csv(clean_filename, index=False)
                print(f"  Clean file: {clean_filename}")
                
                return {
                    'original_count': original_count,
                    'unique_count': len(unique_leads),
                    'duplicate_count': len(duplicates),
                    'duplicate_file': duplicate_filename,
                    'clean_file': clean_filename,
                    'duplicate_rate': (len(duplicates)/original_count)*100
                }
            else:
                print(f"\n✅ No duplicates found! File is already clean.")
                return {
                    'original_count': original_count,
                    'unique_count': len(unique_leads),
                    'duplicate_count': 0,
                    'duplicate_rate': 0
                }
                
        except Exception as e:
            print(f"❌ Error analyzing file: {e}")
            return None
    
    def nuclear_classify(self, lead_data, filepath):
        """NUCLEAR: Aggressive classification that cannot be overridden"""
        
        # 🚀 NUCLEAR RULE 1: Filename-based classification (ABSOLUTE)
        filename_lower = filepath.lower()
        
        # YouTube fitness customers = ALWAYS end customer
        if 'youtube_fitness_customers' in filename_lower:
            return 'end_customer'
        
        # TikTok fitness customers = ALWAYS end customer  
        if 'tiktok_fitness_customers' in filename_lower:
            return 'end_customer'
        
        # Reddit fitness customers = ALWAYS end customer
        if 'reddit_fitness_customers' in filename_lower:
            return 'end_customer'
        
        # Any fitness customers = ALWAYS end customer  
        if 'fitness_customers' in filename_lower:
            return 'end_customer'
        
        # Any _customers file = ALWAYS end customer
        if '_customers' in filename_lower and 'fitness' in filename_lower:
            return 'end_customer'
        
        # 🚀 NUCLEAR RULE 2: Column-based classification (ABSOLUTE)
        if 'customer_type' in lead_data:
            customer_type = str(lead_data['customer_type']).lower()
            if 'end_customer' in customer_type or 'fitness_end_customer' in customer_type:
                return 'end_customer'
        
        if 'business_target' in lead_data:
            business_target = str(lead_data['business_target']).lower()
            if 'end_customer' in business_target:
                return 'end_customer'
        
        # 🚀 NUCLEAR RULE 3: Lead quality indicates end customer
        if 'lead_quality' in lead_data:
            lead_quality = str(lead_data['lead_quality']).lower()
            if lead_quality in ['premium', 'standard', 'volume']:
                return 'end_customer'
        
        # Default: business classification for all other files
        return 'target_business'
    
    def categorize_niche(self, lead_data):
        """Categorize a lead into a niche based on available data"""
        text_fields = []
        fields_to_check = ['bio', 'title', 'search_term', 'name', 'handle']
        
        for field in fields_to_check:
            if field in lead_data and lead_data[field]:
                text_fields.append(str(lead_data[field]).lower())
        
        combined_text = ' '.join(text_fields)
        
        # Score each niche based on keyword matches
        niche_scores = {}
        for niche, keywords in self.niche_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    score += 1
            niche_scores[niche] = score
        
        # Return the niche with highest score, or 'general' if no matches
        if max(niche_scores.values()) > 0:
            return max(niche_scores.items(), key=lambda x: x[1])[0]
        else:
            return 'general'
    
    def find_lead_files(self):
        """Find all lead CSV files"""
        patterns = [
            '*leads*.csv', '*_leads_*.csv', 
            '*fitness_customers*.csv', '*_customers_*.csv',
            'facebook_*.csv', 'instagram_*.csv', 'twitter_*.csv', 
            'linkedin_*.csv', 'youtube_*.csv', 'tiktok_*.csv', 'medium_*.csv',
            'reddit_*.csv', '*scraper*.csv', '*extracted*.csv'
        ]
        
        found_files = []
        for pattern in patterns:
            files = glob.glob(pattern)
            found_files.extend(files)
        
        return list(set(found_files))
    
    def identify_platform(self, filename):
        """Identify platform from filename"""
        filename_lower = filename.lower()
        
        for platform in self.platforms:
            if platform in filename_lower:
                # Determine if it's end customer or business leads
                if any(keyword in filename_lower for keyword in ['fitness_customers', 'end_customer', '_ec_', 'customers']):
                    return f"{platform}_end_customers"
                else:
                    return platform
        
        return 'unknown'
    
    def print_table(self, headers, rows, title=""):
        """Print a formatted table"""
        if title:
            print(f"\n📊 {title}")
            print("=" * len(title))
        
        # Calculate column widths
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(str(header))
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(min(max_width + 2, 20))  # Cap at 20 chars
        
        # Print header
        header_row = " | ".join(str(headers[i]).ljust(col_widths[i]) for i in range(len(headers)))
        print(f"\n{header_row}")
        print("-" * len(header_row))
        
        # Print rows
        for row in rows:
            formatted_row = []
            for i in range(len(headers)):
                if i < len(row):
                    cell = str(row[i])
                    if len(cell) > col_widths[i]:
                        cell = cell[:col_widths[i]-3] + "..."
                    formatted_row.append(cell.ljust(col_widths[i]))
                else:
                    formatted_row.append(" ".ljust(col_widths[i]))
            print(" | ".join(formatted_row))
    
    def generate_organized_report(self):
        """Generate organized report with tables including duplicate stats"""
        print("\n" + "="*80)
        print("📈 ORGANIZED LEAD ANALYSIS REPORT (WITH DUPLICATE DETECTION)")
        print("="*80)
        
        # Calculate totals
        total_leads = sum(self.platform_stats.values())
        total_files = len(self.file_stats)
        total_end_customers = self.business_type_stats.get('end_customer', 0)
        total_businesses = self.business_type_stats.get('target_business', 0)
        
        # Calculate duplicate totals
        total_duplicates_removed = sum(stats['total_duplicates'] for stats in self.duplicate_stats.values())
        total_original_leads = sum(stats['original_count'] for stats in self.duplicate_stats.values())
        
        # Summary section
        print(f"\n🎯 EXECUTIVE SUMMARY")
        print(f"  📁 Total Files: {total_files}")
        print(f"  👥 Original Leads: {total_original_leads:,}")
        print(f"  🧹 Duplicates Removed: {total_duplicates_removed:,}")
        print(f"  ✅ Clean Leads: {total_leads:,}")
        print(f"  🔄 Duplicate Rate: {(total_duplicates_removed/total_original_leads*100) if total_original_leads > 0 else 0:.1f}%")
        print(f"  🏢 Tool Buyers: {total_businesses:,} ({total_businesses/total_leads*100 if total_leads > 0 else 0:.1f}%)")
        print(f"  💥 Lead Inventory: {total_end_customers:,} ({total_end_customers/total_leads*100 if total_leads > 0 else 0:.1f}%)")
        print(f"  📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Duplicate summary table
        if total_duplicates_removed > 0:
            duplicate_rows = []
            for filepath, dup_stats in self.duplicate_stats.items():
                if dup_stats['total_duplicates'] > 0:
                    filename = os.path.basename(filepath)
                    duplicate_rate = (dup_stats['total_duplicates'] / dup_stats['original_count'] * 100)
                    duplicate_rows.append([
                        filename[:25],
                        f"{dup_stats['original_count']:,}",
                        f"{dup_stats['total_duplicates']:,}",
                        f"{dup_stats['unique_leads']:,}",
                        f"{duplicate_rate:.1f}%",
                        dup_stats['duplicate_file'].split('/')[-1] if dup_stats['duplicate_file'] else "N/A"
                    ])
            
            if duplicate_rows:
                self.print_table(
                    ["File", "Original", "Duplicates", "Clean", "Dup Rate", "Export File"],
                    duplicate_rows,
                    "DUPLICATE DETECTION RESULTS"
                )
        
        # Platform breakdown table
        platform_rows = []
        sorted_platforms = sorted(self.platform_stats.items(), key=lambda x: x[1], reverse=True)
        
        for platform, count in sorted_platforms:
            percentage = (count / total_leads * 100) if total_leads > 0 else 0
            
            # Determine platform type
            if 'end_customer' in platform:
                clean_platform = platform.replace('_end_customers', '')
                platform_type = "End Customers"
            else:
                clean_platform = platform
                platform_type = "Mixed/Business"
            
            platform_rows.append([
                clean_platform.title(),
                platform_type,
                f"{count:,}",
                f"{percentage:.1f}%"
            ])
        
        self.print_table(
            ["Platform", "Type", "Leads", "Percentage"],
            platform_rows,
            "PLATFORM BREAKDOWN"
        )
        
        # Niche breakdown table
        niche_rows = []
        sorted_niches = sorted(self.niche_stats.items(), key=lambda x: x[1], reverse=True)
        
        for niche, count in sorted_niches:
            percentage = (count / total_leads * 100) if total_leads > 0 else 0
            niche_display = niche.replace('_', ' ').title()
            
            niche_rows.append([
                niche_display,
                f"{count:,}",
                f"{percentage:.1f}%"
            ])
        
        self.print_table(
            ["Niche", "Leads", "Percentage"],
            niche_rows,
            "NICHE BREAKDOWN"
        )
        
        # Business model analysis
        if total_businesses > 0 and total_end_customers > 0:
            leads_per_client = total_end_customers / total_businesses
            tool_revenue = total_businesses * 97
            lead_value = total_end_customers * 5
            
            business_rows = [
                ["Tool Subscription Revenue", f"${tool_revenue:,}/month", f"{total_businesses:,} prospects @ $97/month"],
                ["Lead Inventory Value", f"${lead_value:,}/month", f"{total_end_customers:,} leads @ $5 each"],
                ["Total Ecosystem Value", f"${tool_revenue + lead_value:,}/month", "Combined revenue potential"],
                ["Leads per Client Ratio", f"{leads_per_client:.1f}", "End customers per business client"],
                ["Model Health", "Good" if leads_per_client >= 10 else "Needs More End Customers", "Assessment based on lead ratio"]
            ]
            
            self.print_table(
                ["Metric", "Value", "Description"],
                business_rows,
                "BUSINESS MODEL ANALYSIS"
            )
        
        # File details table
        file_rows = []
        for filepath, stats in self.file_stats.items():
            filename = os.path.basename(filepath)
            platform_name = stats['platform'].replace('_end_customers', '').title()
            
            # Get business breakdown
            business_breakdown = stats.get('business_target_breakdown', {})
            end_customers = business_breakdown.get('end_customer', 0)
            businesses = business_breakdown.get('target_business', 0)
            
            file_type = "End Customers" if stats.get('is_end_customer_file', False) else "Mixed/Business"
            duplicates_removed = stats.get('duplicates_removed', 0)
            
            file_rows.append([
                filename[:25],
                platform_name,
                file_type,
                f"{stats['total_leads']:,}",
                f"{duplicates_removed:,}" if duplicates_removed > 0 else "0",
                f"{end_customers:,}",
                f"{businesses:,}",
                stats['modified'].strftime('%m/%d %H:%M')
            ])
        
        # Sort by total leads descending
        file_rows.sort(key=lambda x: int(x[3].replace(',', '')), reverse=True)
        
        self.print_table(
            ["File", "Platform", "Type", "Clean", "Dups", "End Cust", "Business", "Modified"],
            file_rows,
            "FILE DETAILS"
        )
        
        # Platform vs Niche cross-analysis table
        if len(sorted_platforms) > 0 and len(sorted_niches) > 0:
            top_platforms = [p[0] for p in sorted_platforms[:5]]
            top_niches = [n[0] for n in sorted_niches[:4]]
            
            cross_rows = []
            for platform in top_platforms:
                clean_platform = platform.replace('_end_customers', '')
                row = [clean_platform.title()]
                
                for niche in top_niches:
                    count = self.platform_niche_stats[platform][niche]
                    row.append(f"{count:,}" if count > 0 else "0")
                
                total = self.platform_stats[platform]
                row.append(f"{total:,}")
                cross_rows.append(row)
            
            headers = ["Platform"] + [n.replace('_', ' ').title()[:10] for n in top_niches] + ["Total"]
            
            self.print_table(
                headers,
                cross_rows,
                "PLATFORM vs NICHE ANALYSIS"
            )
        
        # Strategic recommendations
        print(f"\n💡 STRATEGIC RECOMMENDATIONS")
        print("=" * 30)
        
        if total_duplicates_removed > 0:
            print(f"🧹 DATA QUALITY:")
            print(f"   • Removed {total_duplicates_removed:,} duplicate leads")
            print(f"   • Saved time and improved targeting accuracy")
            print(f"   • Duplicate rate: {(total_duplicates_removed/total_original_leads*100):.1f}%")
        
        if total_end_customers > 0 and total_businesses > 0:
            leads_per_client = total_end_customers / total_businesses
            
            if leads_per_client < 10:
                print("🎯 PRIORITY: Increase end customer collection")
                print(f"   • Current: {leads_per_client:.1f} leads per business client")
                print(f"   • Target: 50+ leads per business client")
                print(f"   • Need: {total_businesses * 50 - total_end_customers:,} more end customers")
            elif leads_per_client > 100:
                print("🏢 PRIORITY: Acquire more business clients")
                print(f"   • Excellent lead inventory: {total_end_customers:,} end customers")
                print(f"   • Can support: {total_end_customers // 50:,} business clients")
            else:
                print("✅ BALANCED: Good ratio of businesses to lead inventory")
        
        if sorted_platforms:
            top_platform = sorted_platforms[0]
            print(f"\n📈 Platform Focus: {top_platform[0].replace('_end_customers', '').title()}")
            print(f"   • Best volume: {top_platform[1]:,} leads")
        
        if sorted_niches:
            top_niche = sorted_niches[0]
            print(f"\n🎯 Niche Focus: {top_niche[0].replace('_', ' ').title()}")
            print(f"   • Strongest performance: {top_niche[1]:,} leads")
        
        return {
            'total_leads': total_leads,
            'total_businesses': total_businesses,
            'total_end_customers': total_end_customers,
            'total_duplicates_removed': total_duplicates_removed,
            'platform_stats': dict(self.platform_stats),
            'niche_stats': dict(self.niche_stats)
        }
    
    def export_organized_summary(self, filename=None):
        """Export organized summary to CSV"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"organized_lead_summary_{timestamp}.csv"
        
        # Platform summary
        platform_data = []
        for platform, count in self.platform_stats.items():
            clean_platform = platform.replace('_end_customers', '')
            platform_type = "End Customers" if 'end_customer' in platform else "Mixed/Business"
            
            platform_data.append({
                'category': 'Platform',
                'name': clean_platform,
                'type': platform_type,
                'total_leads': count,
                'percentage': (count / sum(self.platform_stats.values()) * 100) if sum(self.platform_stats.values()) > 0 else 0
            })
        
        # Niche summary
        niche_data = []
        for niche, count in self.niche_stats.items():
            niche_data.append({
                'category': 'Niche',
                'name': niche.replace('_', ' ').title(),
                'type': 'All Platforms',
                'total_leads': count,
                'percentage': (count / sum(self.niche_stats.values()) * 100) if sum(self.niche_stats.values()) > 0 else 0
            })
        
        # Combine and save
        all_data = platform_data + niche_data
        df = pd.DataFrame(all_data)
        df.to_csv(filename, index=False)
        
        print(f"\n💾 Organized summary exported to: {filename}")
        return filename
    
    def run_organized_analysis(self):
        """Run complete organized analysis with duplicate detection"""
        print("🚀 Starting Organized Lead Analysis with Duplicate Detection...")
        print("=" * 60)
        
        files = self.find_lead_files()
        
        if not files:
            print("❌ No lead files found!")
            return None
        
        print(f"📁 Found {len(files)} files to analyze")
        
        for file in files:
            self.analyze_file_with_duplicates(file)
        
        report = self.generate_organized_report()
        self.export_organized_summary()
        
        return report

def main():
    """Main function with menu options"""
    analyzer = OrganizedLeadAnalyzer()
    
    print("🔍 LEAD ANALYZER WITH DUPLICATE DETECTION")
    print("=" * 50)
    print("1. Analyze all lead files (with duplicate removal)")
    print("2. Analyze specific file for duplicates only") 
    print("3. Find lead files in directory")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        results = analyzer.run_organized_analysis()
        
        if results:
            print(f"\n🎉 ANALYSIS COMPLETE!")
            print(f"📊 {results['total_leads']:,} clean leads analyzed")
            print(f"🧹 {results['total_duplicates_removed']:,} duplicates removed")
            print(f"🏢 {results['total_businesses']:,} business prospects")
            print(f"💥 {results['total_end_customers']:,} end customer leads")
    
    elif choice == "2":
        # Get file path from user
        filepath = input("Enter CSV file path: ").strip()
        
        # Remove quotes if user copied path with quotes
        if filepath.startswith('"') and filepath.endswith('"'):
            filepath = filepath[1:-1]
        elif filepath.startswith("'") and filepath.endswith("'"):
            filepath = filepath[1:-1]
        
        result = analyzer.analyze_single_file_for_duplicates(filepath)
        
        if result:
            print(f"\n🎉 DUPLICATE ANALYSIS COMPLETE!")
            print(f"📊 Processed {result['original_count']:,} leads")
            print(f"🧹 Found {result['duplicate_count']:,} duplicates ({result['duplicate_rate']:.1f}%)")
            print(f"✅ {result['unique_count']:,} unique leads remain")
    
    elif choice == "3":
        files = analyzer.find_lead_files()
        print(f"\n📁 Found {len(files)} lead files:")
        for i, file in enumerate(files, 1):
            print(f"  {i}. {file}")
    
    else:
        print("Invalid choice. Please run again and select 1, 2, or 3.")

if __name__ == "__main__":
    main()