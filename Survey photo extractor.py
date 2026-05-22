import os
import re
import zipfile
import shutil

# Directory Configurations
INPUT_ZIPS_DIR = "input_zips"
EXTRACT_TEMP_DIR = "temp_extracted_workspace"
MASTER_OUTPUT_DIR = "organised_survey_photos"

# Flexible regular expression to normalize and catch various structural block formats:
# Matches 'Blk 514 #09-270', 'Block-515#03-258', 'Block. 521#10---160', 'Block..524#04--50', 'Block..528#2--98'
location_pattern = re.compile(
    r'(?:Blk|Block)[\s.-]*(\w+)\s*#\s*([\w\d\s-]+)', 
    re.IGNORECASE
)

# Captures attachment files embedded within line streams safely
photo_pattern = re.compile(r'<attached:\s*([^>]+\.(?:jpg|jpeg|png|gif|pdf))>', re.IGNORECASE)

# Captures standard phone-exported log timeline headers: e.g., "[14/7/25, 4:00:36 PM] Sender Name:"
msg_header_pattern = re.compile(r'^\[?(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}:\d{2}(?:\s*[AP]M)?)[\]\s:]+([^:]+):')


def clean_unit_string(unit_str):
    """Normalizes whitespace and condenses multiple hyphens down to standard dashes."""
    cleaned = unit_str.strip().replace(" ", "")
    cleaned = re.sub(r'-+', '-', cleaned)
    # Extract only the foundational alphanumeric structure (e.g. 03-44) away from multi-line clutter
    match = re.match(r'^([\d\w]+-[\d\w]+)', cleaned)
    if match:
        return match.group(1)
    return cleaned.split()[0] if cleaned.split() else cleaned


def process_chat_and_media(chat_file_path, media_search_dir, zip_output_dir):
    """
    Parses chat transcripts as structural blocks instead of relying on timestamps.
    Maintains a reliable sequential mapping structure perfect for bulk uploads.
    """
    # Step 1: Consolidate the entire chat into an ordered list of clean message objects
    messages = []
    current_msg = None

    with open(chat_file_path, 'r', encoding='utf-8', errors='ignore') as file:
        for line in file:
            clean_line = line.replace('\u200e', '').replace('\u202f', ' ').strip()
            if not clean_line:
                continue

            header_match = msg_header_pattern.search(clean_line)
            if header_match:
                if current_msg:
                    messages.append(current_msg)
                
                _, _, sender = header_match.groups()
                content = msg_header_pattern.sub('', clean_line).strip()
                
                current_msg = {
                    'sender': sender.strip(),
                    'text': content,
                    'photos': photo_pattern.findall(content)
                }
            else:
                if current_msg:
                    current_msg['text'] += "\n" + clean_line
                    # Catch photo links that span across multi-line text blocks
                    current_msg['photos'].extend(photo_pattern.findall(clean_line))
                    
        if current_msg:
            messages.append(current_msg)

    # Step 2: Use an active state mapping layer to trace structural layout markers
    # Maps user handles directly to their last declared block and unit configuration
    user_states = {}

    for i, msg in enumerate(messages):
        sender = msg['sender']
        text_content = msg['text']
        
        # Look for location descriptions anywhere inside this text entry block
        loc_match = location_pattern.search(text_content)
        
        if loc_match:
            block_num = loc_match.group(1).strip().upper()
            unit_num = clean_unit_string(loc_match.group(2))
            
            # Update state for this specific user
            user_states[sender] = (block_num, unit_num)
            
            # LOOKBACK LOGIC FOR BULK DUMPS:
            # If this message was a text description sent immediately AFTER a sequence of photo messages
            # by the same surveyor, look back up to 15 messages and retroactively assign them.
            for j in range(max(0, i - 15), i):
                prev_msg = messages[j]
                if prev_msg['sender'] == sender and prev_msg['photos']:
                    target_folder = os.path.join(zip_output_dir, f"Block_{block_num}", f"Unit_{unit_num}")
                    for photo in prev_msg['photos']:
                        copy_media_file(photo.strip(), media_search_dir, target_folder)
                    # Clear the photos from that message so they aren't processed twice
                    prev_msg['photos'] = []

        # FORWARD LOGIC FOR BULK DUMPS:
        # Assign photos found in this message or subsequent textless updates to the active user state
        if msg['photos']:
            if sender in user_states:
                active_block, active_unit = user_states[sender]
                target_folder = os.path.join(zip_output_dir, f"Block_{active_block}", f"Unit_{active_unit}")
                for photo in msg['photos']:
                    copy_media_file(photo.strip(), media_search_dir, target_folder)
            else:
                # No active user context found anywhere nearby; route safely to Unsorted
                target_folder = os.path.join(zip_output_dir, "Unsorted_Photos")
                for photo in msg['photos']:
                    copy_media_file(photo.strip(), media_search_dir, target_folder)


def copy_media_file(filename, search_dir, target_folder):
    """Finds exact media matches within the subfolder workspace structure and copies them."""
    source_path = None
    for root, dirs, files in os.walk(search_dir):
        if filename in files:
            source_path = os.path.join(root, filename)
            break
            
    if source_path and os.path.exists(source_path):
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        shutil.copy2(source_path, os.path.join(target_folder, filename))


def main():
    if not os.path.exists(INPUT_ZIPS_DIR):
        print(f"Error: Target root source directory '{INPUT_ZIPS_DIR}' not found.")
        return

    zip_files = [f for f in os.listdir(INPUT_ZIPS_DIR) if f.lower().endswith('.zip')]
    if not zip_files:
        print("No input zip data archives detected.")
        return

    if not os.path.exists(MASTER_OUTPUT_DIR):
        os.makedirs(MASTER_OUTPUT_DIR)

    for zip_file in zip_files:
        zip_path = os.path.join(INPUT_ZIPS_DIR, zip_file)
        zip_base_name = os.path.splitext(zip_file)[0]
        zip_output_dir = os.path.join(MASTER_OUTPUT_DIR, f"{zip_base_name}_survey_organised")
        
        print(f"Executing End-of-Shift Vector Stack Parser on: {zip_file}...")
        
        if os.path.exists(EXTRACT_TEMP_DIR):
            shutil.rmtree(EXTRACT_TEMP_DIR)
        os.makedirs(EXTRACT_TEMP_DIR)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_TEMP_DIR)
            
        chat_log_path = None
        for root, dirs, files in os.walk(EXTRACT_TEMP_DIR):
            if "_chat.txt" in files:
                chat_log_path = os.path.join(root, "_chat.txt")
                break
        
        if chat_log_path:
            process_chat_and_media(chat_log_path, EXTRACT_TEMP_DIR, zip_output_dir)
            print(f"Data mapping execution complete for: {zip_file}")
        else:
            print(f"Error: Archive payload missing text log file: {zip_file}")
            
    if os.path.exists(EXTRACT_TEMP_DIR):
        shutil.rmtree(EXTRACT_TEMP_DIR)
    print(f"\nAll operations finalized. Outputs structured cleanly under '{MASTER_OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()