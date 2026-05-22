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

# --- REGEX PATTERNS ---
# Captures photo filenames
FILE_REGEX = re.compile(r"attached:\s?(\d+-PHOTO-.*?\.jpg)")
# Captures Block and Unit (e.g., Blk 701 #10-11 & 10-12)
LABEL_REGEX = re.compile(r"Blk\s?(\d+)\s?#([\d\-\s&,]+)", re.IGNORECASE)

def process_whatsapp_zip(zip_path):
    start_time = time.time()
    zip_filename = os.path.basename(zip_path)
    project_name = zip_filename.replace('WhatsApp Chat - ', '').replace('.zip', '')
    print(f"\n[PROCESSING] {project_name}")

    # Initialize folders
    if os.path.exists(EXTRACT_FOLDER): shutil.rmtree(EXTRACT_FOLDER)
    os.makedirs(EXTRACT_FOLDER)
    
    # Each project gets its own subfolder inside Organized_Backups
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

    # 3. Read and Clean invisible characters
    with open(chat_path, 'r', encoding='utf-8') as f:
        content = f.read().replace('\u200e', '')

    # 4. Map Positions
    images = [(m.start(), m.group(1).strip()) for m in re.finditer(FILE_REGEX, content)]
    labels = list(re.finditer(LABEL_REGEX, content))

    image_idx = 0
    moved_count = 0

    # 5. Logic: Iterate through labels and capture images sent BEFORE them
    for m in labels:
        label_pos = m.start()
        block = m.group(1)
        unit_raw = m.group(2)

        # Split units if multiple are mentioned (e.g., 10-11 & 10-12)
        units = re.split(r'[&,]', unit_raw)
        units = [u.strip().replace('-', '_') for u in units if u.strip()]

        for unit in units:
            target_dir = os.path.join(project_output, f"Blk_{block}", f"Unit_{unit}")
            os.makedirs(target_dir, exist_ok=True)

            # Copy photos to each unit folder mentioned in the line
            temp_idx = image_idx
            while temp_idx < len(images) and images[temp_idx][0] < label_pos:
                img_name = images[temp_idx][1]
                src = os.path.join(EXTRACT_FOLDER, img_name)
                dst = os.path.join(target_dir, img_name)
                
                if os.path.exists(src):
                    # Use copy2 to allow the same photo to appear in multiple unit folders
                    shutil.copy2(src, dst)
                    moved_count += 1
                temp_idx += 1
        
        # Advance the master pointer to skip images already assigned to the previous anchor
        while image_idx < len(images) and images[image_idx][0] < label_pos:
            image_idx += 1
            
    # Cleanup temp extraction (but keeping all organized folders, even empty ones)
    shutil.rmtree(EXTRACT_FOLDER)
    print(f"[SUCCESS] {project_name} processed.")
    print(f"Photos Organized: {moved_count}")
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