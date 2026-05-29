import os
import re
import shutil
import zipfile
import time
import glob

# --- CONFIGURATION ---
INPUT_FOLDER = 'input_zips' 
EXTRACT_FOLDER = 'temp_raw_photos'
OUTPUT_ROOT = 'Organized_Backups_2A'

# Matches BOTH Android ("filename.ext (file attached)") and iOS ("<attached: filename.ext>") styles
FILE_REGEX = re.compile(
    r"(?:<attached:\s*([^>\s]+\.(?:jpg|mp4|png|jpeg))>)|(?:([\w\d\-]+\.(?:jpg|mp4|png|jpeg))\s?\(file attached\))", 
    re.IGNORECASE
)

# MODIFIED REGEX: Matches "Blk 448#09-533" AND "Blk 451-12-557"
# Group 1: Block number
# Group 2: The rest of the address identifier string
LABEL_REGEX = re.compile(r"Blk\s?(\d+[A-Z]?)(?:\s?#|-\s?)((?:[\d\-\s&,#]|\d+-\d+-\d+)+)", re.IGNORECASE)

# Matches standard WhatsApp line headers to parse sequentially (with or without brackets)
MSG_HEADER_REGEX = re.compile(
    r"^\[?(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}:\d{2}(?:\s?[AP]M)?)]?\s-[^:]+:\s|^\[?(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}:\d{2}(?:\s?[AP]M)?)]?\s[^:]+:\s", 
    re.IGNORECASE
)

def pad_unit_string(unit_str):
    parts = unit_str.split('_')
    padded_parts = [p.zfill(2) for p in parts if p.isdigit()]
    if len(padded_parts) >= 2:
        return f"{padded_parts[0]}_{padded_parts[1]}"
    return unit_str

def get_unique_filename(target_dir, filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    while os.path.exists(os.path.join(target_dir, unique_filename)):
        unique_filename = f"{name}_{counter}{ext}"
        counter += 1
    return unique_filename

def process_whatsapp_zip(zip_path):
    start_time = time.time()
    zip_filename = os.path.basename(zip_path)
    project_name = zip_filename.replace('WhatsApp Chat - ', '').replace('.zip', '')
    print(f"\n[PROCESSING] {project_name}")

    if os.path.exists(EXTRACT_FOLDER): shutil.rmtree(EXTRACT_FOLDER)
    os.makedirs(EXTRACT_FOLDER)
    
    project_output = os.path.join(OUTPUT_ROOT, project_name)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_FOLDER)

    chat_files = [f for f in os.listdir(EXTRACT_FOLDER) if f.endswith('.txt')]
    if not chat_files:
        print(f"Skipping: No log file found in {zip_filename}")
        return
    
    chat_path = os.path.join(EXTRACT_FOLDER, chat_files[0])

    with open(chat_path, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    # Strip invisible unicode control characters from the entire file BEFORE parsing headers
    cleaned_content = raw_content.replace('\u200e', '').replace('\u200f', '')
    lines = cleaned_content.splitlines()

    # Step 1: Parse content sequentially into structured message blocks
    parsed_messages = []
    current_msg = None

    for line in lines:
        if not line.strip():
            continue
            
        header_match = MSG_HEADER_REGEX.match(line)
        
        if header_match:
            if current_msg:
                parsed_messages.append(current_msg)
            
            body = line[header_match.end():]
            current_msg = {"body": body, "media": [], "label": None}
            
            media_match = FILE_REGEX.search(body)
            if media_match:
                name = media_match.group(1) if media_match.group(1) else media_match.group(2)
                if name: current_msg["media"].append(name.strip())
                
            label_match = LABEL_REGEX.search(body)
            if label_match:
                current_msg["label"] = label_match.group(0)
        else:
            if current_msg:
                current_msg["body"] += "\n" + line
                label_match = LABEL_REGEX.search(line)
                if label_match:
                    current_msg["label"] = label_match.group(0)
                media_match = FILE_REGEX.search(line)
                if media_match:
                    name = media_match.group(1) if media_match.group(1) else media_match.group(2)
                    if name: current_msg["media"].append(name.strip())

    if current_msg:
        parsed_messages.append(current_msg)

    # Step 2: Strict Look-Ahead buffering strategy
    label_assignments = []
    media_buffer = []

    for msg in parsed_messages:
        if msg["media"]:
            media_buffer.extend(msg["media"])
            
        if msg["label"]:
            label_assignments.append({
                "label_raw": msg["label"],
                "media": list(dict.fromkeys(media_buffer))  # Keeps unique files in chronological order
            })
            media_buffer = []  # Clear out buffer for the next address block sequence

    # Step 3: Map files into target file directories
    moved_count = 0
    
    for item in label_assignments:
        label_match = LABEL_REGEX.search(item["label_raw"])
        if not label_match: continue
        
        block = label_match.group(1).upper().strip() 
        unit_raw = label_match.group(2).strip()

        # Split multiple units using commas, ampersands, or extra hashes
        units = re.split(r'[&,#]', unit_raw)
        cleaned_units = []
        
        for u in units:
            u_clean = u.strip().split('\n')[0].split('\r')[0].strip()
            if not u_clean:
                continue
                
            # SPECIAL CASE: Converts "12-557" (from Blk 451-12-557) into "12_557"
            # It checks if the string contains only digits and hyphens (standard floor-unit sequence)
            if '-' in u_clean and u_clean.replace('-', '').isdigit():
                u_clean = u_clean.replace('-', '_')
            else:
                u_clean = u_clean.replace('-', '_')

            if u_clean:
                cleaned_units.append(pad_unit_string(u_clean))

        for unit in cleaned_units:
            target_dir = os.path.join(project_output, f"Blk_{block}", f"Unit_{unit}")
            os.makedirs(target_dir, exist_ok=True)

            for media_name in item["media"]:
                src = os.path.join(EXTRACT_FOLDER, media_name)
                actual_file = None
                if os.path.exists(src):
                    actual_file = src
                else:
                    base_search = glob.glob(os.path.join(EXTRACT_FOLDER, f"*{media_name}"))
                    if base_search: actual_file = base_search[0]

                if actual_file and os.path.exists(actual_file):
                    safe_media_name = get_unique_filename(target_dir, os.path.basename(actual_file))
                    dst = os.path.join(target_dir, safe_media_name)
                    shutil.copy2(actual_file, dst)
                    moved_count += 1
            
    shutil.rmtree(EXTRACT_FOLDER)
    print(f"[SUCCESS] Checked out project folders perfectly.")
    print(f"Total media items structured correctly: {moved_count}")
    print(f"Execution Duration: {round(time.time() - start_time, 2)}s")

def main():
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"Created folder structure. Add your zip files inside '{INPUT_FOLDER}' and re-run.")
        return
    all_zips = glob.glob(os.path.join(INPUT_FOLDER, "*.zip"))
    if not all_zips:
        print(f"No archive packages found inside '{INPUT_FOLDER}'.")
        return
    for zip_file in all_zips:
        process_whatsapp_zip(zip_file)

if __name__ == "__main__":
    main()