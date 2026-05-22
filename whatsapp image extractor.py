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

# --- IMPROVED REGEX PATTERNS ---
FILE_REGEX = re.compile(r"attached:\s?(\d+-PHOTO-.*?\.jpg)")

# UPDATED: Captures digits followed by optional letters (e.g., 506, 506A, 506B)
LABEL_REGEX = re.compile(r"Blk\s?(\d+[A-Z]?)\s?#([\d\-\s&,]+)", re.IGNORECASE)

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
        content = f.read().replace('\u200e', '')

    images = [(m.start(), m.group(1).strip()) for m in re.finditer(FILE_REGEX, content)]
    labels = list(re.finditer(LABEL_REGEX, content))

    image_idx = 0
    moved_count = 0

    for m in labels:
        label_pos = m.start()
        block = m.group(1).upper() # Ensure Block 506a becomes 506A
        unit_raw = m.group(2)

        units = re.split(r'[&,]', unit_raw)
        units = [u.strip().replace('-', '_') for u in units if u.strip()]

        for unit in units:
            # Folder name will now handle Blk_506A correctly
            target_dir = os.path.join(project_output, f"Blk_{block}", f"Unit_{unit}")
            os.makedirs(target_dir, exist_ok=True)

            temp_idx = image_idx
            while temp_idx < len(images) and images[temp_idx][0] < label_pos:
                img_name = images[temp_idx][1]
                src = os.path.join(EXTRACT_FOLDER, img_name)
                dst = os.path.join(target_dir, img_name)
                
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                    moved_count += 1
                temp_idx += 1
        
        while image_idx < len(images) and images[image_idx][0] < label_pos:
            image_idx += 1
            
    shutil.rmtree(EXTRACT_FOLDER)
    print(f"[SUCCESS] {project_name} processed.")
    print(f"Photos Organized: {moved_count}")
    print(f"Time Taken: {round(time.time() - start_time, 2)}s")

def main():
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        return

    all_zips = glob.glob(os.path.join(INPUT_FOLDER, "*.zip"))
    for zip_file in all_zips:
        process_whatsapp_zip(zip_file)

if __name__ == "__main__":
    main()