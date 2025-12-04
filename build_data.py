import csv
import json
import os
import math

# --- CONFIGURATION ---
CSV_FILENAME = 'episodes (1).csv' 
DEFAULT_IPFS_ROOT = "QmYoi9yujdACiLyxXpVLGJJjR374KktXv4um798b1FZd6A"
CHUNK_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB limit per file

print("--- Starting Build Process ---")

# 1. FIND JSON FILES
print("Scanning for transcripts...")
json_map = {}
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".json"):
            try:
                ep_id = int(file.replace(".json", ""))
                json_map[ep_id] = os.path.join(root, file)
            except ValueError: pass

print(f"Found {len(json_map)} transcript files.")

# 2. BUILD MASTER DATA
master_data = []
try:
    with open(CSV_FILENAME, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='~')
        for row in reader:
            try:
                ep_id = int(float(row.get('episode_id', '').strip()))
            except: continue

            csv_link = row.get('mp3_link', '').strip()
            if "http" in csv_link: audio_url = csv_link
            elif csv_link: audio_url = f"https://ipfs.io/ipfs/{DEFAULT_IPFS_ROOT}/{csv_link.split('/')[-1]}"
            else: audio_url = ""

            full_text = ""
            segments_data = []
            if ep_id in json_map:
                try:
                    with open(json_map[ep_id], 'r', encoding='utf-8') as jf:
                        jdata = json.load(jf)
                        if 'text' in jdata: full_text = jdata['text']
                        elif 'segments' in jdata: full_text = " ".join([s['text'] for s in jdata['segments']])
                        if 'segments' in jdata:
                            for seg in jdata['segments']:
                                segments_data.append({'s': int(seg['start']), 't': seg['text']})
                except: pass

            master_data.append({
                'id': ep_id,
                'title': row.get('title', ''),
                'date': row.get('publish_date', ''),
                'audio': audio_url,
                'search_text': full_text.lower(),
                'segments': segments_data
            })
except FileNotFoundError:
    print(f"ERROR: Could not find '{CSV_FILENAME}'")
    exit()

print(f"Total Episodes: {len(master_data)}")

# 3. SPLIT AND SAVE
import sys
json_str = json.dumps(master_data)
size_mb = sys.getsizeof(json_str) / (1024 * 1024)
print(f"Total Data Size: {size_mb:.2f} MB")

script_tags = []

if size_mb < (CHUNK_SIZE_BYTES / (1024*1024)):
    with open('data.js', 'w', encoding='utf-8') as f:
        f.write(f"window.db = {json_str};")
    script_tags.append('<script src="data.js"></script>')
    print("Saved as single 'data.js'")
else:
    print(f"File too big. Splitting...")
    total_items = len(master_data)
    chunks = math.ceil(size_mb / (CHUNK_SIZE_BYTES / (1024*1024)))
    items_per_chunk = math.ceil(total_items / chunks)
    
    for i in range(chunks):
        start = i * items_per_chunk
        end = start + items_per_chunk
        chunk_data = master_data[start:end]
        filename = f"data_part{i}.js"
        with open(filename, 'w', encoding='utf-8') as f:
            json_chunk = json.dumps(chunk_data)
            f.write(f"window.db = (window.db || []).concat({json_chunk});")
        print(f"  -> Created {filename}")
        script_tags.append(f'<script src="{filename}"></script>')

# 4. AUTOMATICALLY UPDATE HTML FILES
new_scripts_block = "\n    ".join(script_tags)

def update_html_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # Replace logic
        if '<script src="data.js"></script>' in html:
            html = html.replace('<script src="data.js"></script>', new_scripts_block)
        elif 'data_part0.js' in html:
            pass # Already updated
        else:
            # Inject before the first custom script or end of body
            if '<script>' in html:
                html = html.replace('<script>', f"{new_scripts_block}\n    <script>", 1)
            elif '</body>' in html:
                html = html.replace('</body>', f"{new_scripts_block}\n</body>")
            
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"SUCCESS: Updated {filename}")
    except FileNotFoundError:
        print(f"Warning: {filename} not found.")

update_html_file('index.html')
update_html_file('transcript.html')