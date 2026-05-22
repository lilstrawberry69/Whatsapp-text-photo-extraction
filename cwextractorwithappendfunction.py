import os
import re
import shutil
import zipfile
import time
import glob

# --- CONFIGURATION ---
INPUT_FOLDER = 'input_zips' 
EXTRACT_FOLDER = 'temp_raw_photos'
OUTPUT_ROOT = 'Organized_Backups'

# --- TARGETED MULTI-FORMAT LOG PATTERN ---
# UPDATED: Captures both .jpg and .mp4 extensions followed by (file attached)
FILE_REGEX = re.compile(r"([\w\d\-]+\.(?:jpg|mp4))\s?\(file attached\)", re.IGNORECASE)

# Matches address block structures with optional alphanumeric characters (e.g., Blk 517)
LABEL_REGEX = re.compile(r"Blk\s?(\d+[A-Z]?)\s?#([\d\-\s&,]+)", re.IGNORECASE)

def pad_unit_string(unit_str):
    """
    Standardizes a unit string (e.g. '4_238' or '04_238') to use uniform 2-digit 
    zero-padding for both floor and room number components (e.g. '04_238').
    """
    parts = unit_str.split('_')
    padded_parts = [p.zfill(2) for p in parts if p.isdigit()]
    
    if len(padded_parts) >= 2:
        return f"{padded_parts[0]}_{padded_parts[1]}"
    return unit_str

def get_unique_filename(target_dir, filename):
    """
    Prevents overwriting old data if a photo/video with the same filename already 
    exists in the target directory by appending a numerical suffix.
    """
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

    # 1. Extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_FOLDER)

    # 2. Find Chat Log
    chat_files = [f for f in os.listdir(EXTRACT_FOLDER) if f.endswith('.txt')]
    if not chat_files:
        print(f"Skipping: No log file found in {zip_filename}")
        return
    
    chat_path = os.path.join(EXTRACT_FOLDER, chat_files[0])

    # 3. Read and Clean hidden markers completely
    with open(chat_path, 'r', encoding='utf-8') as f:
        content = f.read()
        content = content.replace('\u200e', '').replace('\u200f', '')

    # 4. Map Positions
    media_items = []
    for m in re.finditer(FILE_REGEX, content):
        media_items.append((m.start(), m.group(1).strip()))

    labels = list(re.finditer(LABEL_REGEX, content))

    print(f" -> Found {len(media_items)} media attachments (Images/Videos) in text.")
    print(f" -> Found {len(labels)} structural address blocks.")

    moved_count = 0

    # 5. Reverse Proximity Logic
    for i, current_label in enumerate(labels):
        label_pos = current_label.start()
        
        # Boundary: Only pull media sent after the previous label's position anchor
        prev_label_pos = labels[i-1].start() if i > 0 else 0
        
        block = current_label.group(1).upper().strip() 
        unit_raw = current_label.group(2)

        units = re.split(r'[&,]', unit_raw)
        cleaned_units = []
        for u in units:
            u_clean = u.strip().split('\n')[0].split('\r')[0].strip()
            u_clean = u_clean.replace('-', '_')
            if u_clean:
                padded_unit = pad_unit_string(u_clean)
                cleaned_units.append(padded_unit)

        # Collect images and videos falling into this block's specific log segment window
        targeted_media = [media_name for media_pos, media_name in media_items if prev_label_pos <= media_pos < label_pos]

        for unit in cleaned_units:
            target_dir = os.path.join(project_output, f"Blk_{block}", f"Unit_{unit}")
            os.makedirs(target_dir, exist_ok=True)

            for media_name in targeted_media:
                src = os.path.join(EXTRACT_FOLDER, media_name)
                
                # Check for direct naming or wildcard prefixes added on filesystem extracts
                actual_file = None
                if os.path.exists(src):
                    actual_file = src
                else:
                    base_search = glob.glob(os.path.join(EXTRACT_FOLDER, f"*{media_name}"))
                    if base_search:
                        actual_file = base_search[0]

                if actual_file and os.path.exists(actual_file):
                    safe_media_name = get_unique_filename(target_dir, os.path.basename(actual_file))
                    dst = os.path.join(target_dir, safe_media_name)
                    
                    shutil.copy2(actual_file, dst)
                    moved_count += 1
            
    shutil.rmtree(EXTRACT_FOLDER)
    print(f"[SUCCESS] {project_name} parsed.")
    print(f"Media Files successfully copied to units: {moved_count}")
    print(f"Time Taken: {round(time.time() - start_time, 2)}s")

def main():
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"Created '{INPUT_FOLDER}'. Put your ZIPs there and run again.")
        return

    all_zips = glob.glob(os.path.join(INPUT_FOLDER, "*.zip"))
    if not all_zips:
        print(f"No ZIP files found in '{INPUT_FOLDER}'.")
        return

    for zip_file in all_zips:
        process_whatsapp_zip(zip_file)

if __name__ == "__main__":
    main()