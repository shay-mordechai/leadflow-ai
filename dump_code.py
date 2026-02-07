import os

# קבצים ותיקיות שנתעלם מהם (כדי לא להעמיס על ה-AI בזבל)
EXCLUDE_DIRS = {
    'node_modules', 'venv', '.git', '__pycache__', '.next', 'dist', 'build', '.idea', '.vscode'
}
EXCLUDE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.pyc', '.lock', '.json-lock', '.woff', '.woff2'
}
# קבצים ספציפיים להתעלמות
EXCLUDE_FILES = {
    'package-lock.json', 'yarn.lock', 'poetry.lock', 'dump_code.py', 'leads.db', 'full_codebase.txt'
}

OUTPUT_FILE = "full_codebase.txt"

def is_text_file(filename):
    return not any(filename.endswith(ext) for ext in EXCLUDE_EXTENSIONS)

def main():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        # כותרת ראשית
        outfile.write(f"# FULL CODEBASE DUMP\n")
        outfile.write(f"# Generated for AI Review\n")
        outfile.write("="*50 + "\n\n")

        for root, dirs, files in os.walk("."):
            # סינון תיקיות
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file in EXCLUDE_FILES or not is_text_file(file):
                    continue
                
                file_path = os.path.join(root, file)
                
                # כתיבת שם הקובץ ותוכנו
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        content = infile.read()
                        
                    outfile.write(f"\n\n{'='*20} START OF FILE: {file_path} {'='*20}\n")
                    outfile.write(content)
                    outfile.write(f"\n{'='*20} END OF FILE: {file_path} {'='*20}\n")
                    print(f"✅ Added: {file_path}")
                except Exception as e:
                    print(f"⚠️ Skipped (Error reading): {file_path}")

    print(f"\n🚀 Done! All code saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
