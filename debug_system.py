# debug_system.py - Comprehensive debugging and fixes for production issues
import os
import json
import traceback
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import shutil
import tempfile

class ProductionDebugger:
    """Debug and fix production issues automatically"""
    
    def __init__(self):
        self.debug_log = []
        self.fixes_applied = []
        
    def log(self, message, level="INFO"):
        """Log debug message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.debug_log.append(log_entry)
        print(log_entry)
    
    def comprehensive_system_check(self):
        """Run comprehensive system diagnostics"""
        self.log("🔍 Starting comprehensive system check...")
        
        # Check 1: File system and permissions
        self.check_file_system()
        
        # Check 2: JSON file integrity
        self.check_json_files()
        
        # Check 3: Scraper dependencies
        self.check_scraper_dependencies()
        
        # Check 4: Missing directories and files
        self.check_missing_files()
        
        # Check 5: Python imports
        self.check_python_imports()
        
        return {
            "debug_log": self.debug_log,
            "fixes_applied": self.fixes_applied,
            "status": "completed"
        }
    
    def check_file_system(self):
        """Check file system and permissions"""
        self.log("📁 Checking file system...")
        
        cwd = os.getcwd()
        self.log(f"Working directory: {cwd}")
        
        # Check write permissions
        test_dirs = [Path('.'), Path.home(), Path(tempfile.gettempdir())]
        writable_dirs = []
        
        for test_dir in test_dirs:
            try:
                test_file = test_dir / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()
                writable_dirs.append(str(test_dir))
                self.log(f"✅ {test_dir} is writable")
            except Exception as e:
                self.log(f"❌ {test_dir} not writable: {e}", "ERROR")
        
        if not writable_dirs:
            self.log("🚨 NO WRITABLE DIRECTORIES FOUND!", "CRITICAL")
        
        # List all files in current directory
        try:
            files = list(Path('.').glob('*'))
            self.log(f"Files in current directory: {len(files)}")
            for f in files[:10]:  # Show first 10
                self.log(f"  📄 {f.name}")
        except Exception as e:
            self.log(f"❌ Cannot list files: {e}", "ERROR")
    
    def check_json_files(self):
        """Check and fix JSON file integrity"""
        self.log("🔧 Checking JSON file integrity...")
        
        json_files = [
            "users.json",
            "users_credits.json", 
            "transactions.json",
            "simple_auth_state.json"
        ]
        
        for json_file in json_files:
            self.check_and_fix_json_file(json_file)
    
    def check_and_fix_json_file(self, filename):
        """Check and fix a specific JSON file"""
        filepath = Path(filename)
        
        if not filepath.exists():
            self.log(f"📝 {filename} doesn't exist - will create when needed")
            return
        
        try:
            # Try to read as text first
            content = filepath.read_text(encoding='utf-8')
            if not content.strip():
                self.log(f"📝 {filename} is empty")
                return
            
            # Try to parse as JSON
            json.loads(content)
            self.log(f"✅ {filename} is valid JSON")
            
        except UnicodeDecodeError as e:
            self.log(f"❌ {filename} has encoding issues: {e}", "ERROR")
            self.fix_corrupted_json_file(filepath)
            
        except json.JSONDecodeError as e:
            self.log(f"❌ {filename} has JSON syntax errors: {e}", "ERROR")
            self.fix_corrupted_json_file(filepath)
            
        except Exception as e:
            self.log(f"❌ {filename} check failed: {e}", "ERROR")
    
    def fix_corrupted_json_file(self, filepath):
        """Fix corrupted JSON file"""
        try:
            # Backup corrupted file
            backup_path = filepath.with_suffix(f'.corrupted.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            shutil.copy2(filepath, backup_path)
            self.log(f"💾 Backed up corrupted file to {backup_path}")
            
            # Try to read as binary and clean
            raw_data = filepath.read_bytes()
            
            # Remove null bytes and non-UTF8 characters
            cleaned_data = raw_data.replace(b'\x00', b'').replace(b'\xff', b'')
            
            # Try to extract JSON-like content
            text_data = cleaned_data.decode('utf-8', errors='ignore')
            
            # Look for JSON patterns
            if '{' in text_data and '}' in text_data:
                start = text_data.find('{')
                end = text_data.rfind('}') + 1
                potential_json = text_data[start:end]
                
                try:
                    parsed = json.loads(potential_json)
                    # Success! Write clean JSON
                    filepath.write_text(json.dumps(parsed, indent=4), encoding='utf-8')
                    self.log(f"✅ Recovered and fixed {filepath}")
                    self.fixes_applied.append(f"Recovered JSON data from {filepath}")
                    return
                except:
                    pass
            
            # If recovery fails, create empty JSON based on filename
            if 'users' in filepath.name:
                default_content = '{}'
            elif 'transactions' in filepath.name:
                default_content = '[]'
            else:
                default_content = '{}'
            
            filepath.write_text(default_content, encoding='utf-8')
            self.log(f"🔄 Created clean {filepath} with default content")
            self.fixes_applied.append(f"Reset {filepath} to default")
            
        except Exception as e:
            self.log(f"❌ Failed to fix {filepath}: {e}", "ERROR")
    
    def check_scraper_dependencies(self):
        """Check scraper dependencies and imports"""
        self.log("🤖 Checking scraper dependencies...")
        
        # Check Python packages
        required_packages = [
            'requests', 
            'pandas', 'streamlit'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                self.log(f"✅ {package} imported successfully")
            except ImportError:
                self.log(f"❌ {package} not available", "ERROR")
        
        # Check scraper files
        scraper_files = [
            'instagram_scraper.py',
            'twitter_scraper.py', 
            'linkedin_scraper.py',
            'tiktok_scraper.py',
            'youtube_scraper.py',
            'medium_scraper_ec.py',
            'reddit_scraper_ec.py'
        ]
        
        for scraper_file in scraper_files:
            if Path(scraper_file).exists():
                self.log(f"✅ {scraper_file} exists")
                self.test_scraper_import(scraper_file)
            else:
                self.log(f"❌ {scraper_file} missing", "ERROR")
    
    def test_scraper_import(self, scraper_file):
        """Test if scraper file can be imported"""
        try:
            module_name = scraper_file.replace('.py', '')
            # Use subprocess to test import without affecting current process
            result = subprocess.run([
                sys.executable, '-c', f'import {module_name}; print("Import successful")'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.log(f"✅ {scraper_file} imports successfully")
            else:
                self.log(f"❌ {scraper_file} import failed: {result.stderr}", "ERROR")
                
        except Exception as e:
            self.log(f"❌ Failed to test {scraper_file}: {e}", "ERROR")
    
    def check_missing_files(self):
        """Check for missing directories and files"""
        self.log("📂 Checking for missing directories and files...")
        
        # Directories that scrapers might need
        required_dirs = [
            'dm_library',
            'lead_data', 
            'exports',
            'temp',
            'logs'
        ]
        
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.log(f"📁 Created missing directory: {dir_name}")
                    self.fixes_applied.append(f"Created directory {dir_name}")
                except Exception as e:
                    self.log(f"❌ Cannot create directory {dir_name}: {e}", "ERROR")
            else:
                self.log(f"✅ Directory {dir_name} exists")
    
    def check_python_imports(self):
        """Test all critical Python imports"""
        self.log("🐍 Testing Python imports...")
        
        critical_imports = [
            ('json', 'json'),
            ('os', 'os'),
            ('sys', 'sys'),
            ('pathlib', 'Path'),
            ('datetime', 'datetime'),
            ('streamlit', 'st'),
            ('simple_credit_system', 'credit_system')
        ]
        
        for module, item in critical_imports:
            try:
                if item:
                    exec(f"from {module} import {item}")
                else:
                    exec(f"import {module}")
                self.log(f"✅ Import successful: from {module} import {item}")
            except Exception as e:
                self.log(f"❌ Import failed: from {module} import {item} - {e}", "ERROR")
    
    def create_missing_dm_library(self, username):
        """Create missing DM library file for user"""
        try:
            dm_dir = Path('dm_library')
            dm_dir.mkdir(exist_ok=True)
            
            dm_file = dm_dir / f"{username}_dm_library.json"
            
            default_dms = {
                "instagram": [
                    "Hey! Love your content. Would you be interested in collaborating?",
                    "Hi there! I think we could work together on something amazing.",
                    "Hello! Your profile caught my eye. Let's connect!"
                ],
                "twitter": [
                    "Great tweet! Would love to connect.",
                    "Interesting perspective! Let's chat.",
                    "Love your content! DM me if you want to collaborate."
                ],
                "linkedin": [
                    "I'd like to connect with you on LinkedIn.",
                    "Saw your profile and think we should connect.",
                    "Would love to add you to my professional network."
                ]
            }
            
            dm_file.write_text(json.dumps(default_dms, indent=4), encoding='utf-8')
            self.log(f"✅ Created DM library for {username}")
            self.fixes_applied.append(f"Created DM library for {username}")
            
        except Exception as e:
            self.log(f"❌ Failed to create DM library for {username}: {e}", "ERROR")
    
    def run_scraper_test(self, platform="instagram", username="test_user"):
        """Run a controlled scraper test"""
        self.log(f"🧪 Testing {platform} scraper...")
        
        try:
            # Ensure DM library exists
            self.create_missing_dm_library(username)
            
            # Try to import the scraper
            if platform == "instagram":
                scraper_file = "instagram_scraper.py"
            elif platform == "twitter":
                scraper_file = "twitter_scraper.py"
            else:
                scraper_file = f"{platform}_scraper.py"
            
            if not Path(scraper_file).exists():
                self.log(f"❌ {scraper_file} not found", "ERROR")
                return False
            
            # Test basic import
            module_name = scraper_file.replace('.py', '')
            test_script = f"""
import sys
import traceback
try:
    import {module_name}
    print("IMPORT_SUCCESS")
    # Try to access main function
    if hasattr({module_name}, 'scrape_{platform}'):
        print("FUNCTION_FOUND")
    else:
        print("FUNCTION_MISSING")
except Exception as e:
    print(f"IMPORT_ERROR: {{e}}")
    traceback.print_exc()
"""
            
            result = subprocess.run([
                sys.executable, '-c', test_script
            ], capture_output=True, text=True, timeout=30)
            
            if "IMPORT_SUCCESS" in result.stdout:
                self.log(f"✅ {platform} scraper imports successfully")
                if "FUNCTION_FOUND" in result.stdout:
                    self.log(f"✅ {platform} scraper function found")
                else:
                    self.log(f"⚠️ {platform} scraper function missing", "WARNING")
                return True
            else:
                self.log(f"❌ {platform} scraper import failed", "ERROR")
                self.log(f"Error output: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Scraper test failed: {e}", "ERROR")
            return False
    
    def generate_debug_report(self):
        """Generate comprehensive debug report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "python_version": sys.version,
                "working_directory": os.getcwd(),
                "environment": os.environ.copy()
            },
            "debug_log": self.debug_log,
            "fixes_applied": self.fixes_applied,
            "file_listing": []
        }
        
        # Add file listing
        try:
            for file_path in Path('.').rglob('*'):
                if file_path.is_file():
                    report["file_listing"].append({
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
        except Exception as e:
            self.log(f"❌ Failed to generate file listing: {e}", "ERROR")
        
        return report

# Convenience function for Streamlit
def run_production_debug():
    """Run production debugging and return results"""
    debugger = ProductionDebugger()
    results = debugger.comprehensive_system_check()
    report = debugger.generate_debug_report()
    
    return {
        "results": results,
        "report": report,
        "debugger": debugger
    }

# Quick fix functions
def quick_fix_json_files():
    """Quick fix for JSON file issues"""
    debugger = ProductionDebugger()
    debugger.check_json_files()
    return debugger.fixes_applied

def quick_fix_missing_dirs():
    """Quick fix for missing directories"""
    debugger = ProductionDebugger()
    debugger.check_missing_files()
    return debugger.fixes_applied

def emergency_reset_user_data():
    """Emergency reset of user data files"""
    try:
        # Backup existing files
        backup_dir = Path(f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_dir.mkdir(exist_ok=True)
        
        files_to_reset = [
            "users.json",
            "users_credits.json",
            "transactions.json",
            "simple_auth_state.json"
        ]
        
        for filename in files_to_reset:
            filepath = Path(filename)
            if filepath.exists():
                # Backup
                shutil.copy2(filepath, backup_dir / filename)
                
                # Reset to clean state
                if 'users' in filename:
                    clean_content = '{}'
                elif 'transactions' in filename:
                    clean_content = '[]'
                else:
                    clean_content = '{}'
                
                filepath.write_text(clean_content, encoding='utf-8')
        
        return f"✅ Emergency reset completed. Backup saved to {backup_dir}"
        
    except Exception as e:
        return f"❌ Emergency reset failed: {e}"