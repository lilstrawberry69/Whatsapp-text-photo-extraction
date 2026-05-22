import os
from statistics import mean, mode, StatisticsError

# --- CONFIGURATION ---
PARENT_DIR = 'Organized_Backups'

def validate_with_detailed_outliers():
    if not os.path.exists(PARENT_DIR):
        print(f"Error: Folder '{PARENT_DIR}' not found.")
        return

    projects = [d for d in os.listdir(PARENT_DIR) if os.path.isdir(os.path.join(PARENT_DIR, d))]
    
    for project in projects:
        target_dir = os.path.join(PARENT_DIR, project)
        
        print(f"\n{'='*95}")
        print(f"VALIDATION & OUTLIER ANALYSIS: {project}")
        print(f"{'='*95}")
        print(f"{'Block':<15} | {'Units':<8} | {'Empty':<8} | {'Avg Photos'} | {'Status'}")
        print("-" * 95)

        all_block_data = []
        global_counts = []

        # 1. Data Collection
        blocks = sorted([d for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))])
        for block in blocks:
            block_path = os.path.join(target_dir, block)
            units = sorted([u for u in os.listdir(block_path) if os.path.isdir(os.path.join(block_path, u))])
            
            block_units_info = []
            for unit in units:
                unit_path = os.path.join(block_path, unit)
                count = len([f for f in os.listdir(unit_path) if not f.startswith('.')])
                block_units_info.append({'name': unit, 'count': count})
                global_counts.append(count)

            avg_photos = mean([u['count'] for u in block_units_info]) if block_units_info else 0
            all_block_data.append({
                'block_name': block,
                'units': block_units_info,
                'avg': avg_photos
            })

        # 2. Determine Project Standard (Mode is often better than Mean for work-logs)
        try:
            project_standard = mode([c for c in global_counts if c > 0])
        except StatisticsError:
            project_standard = round(mean(global_counts)) if global_counts else 0

        # 3. Print Block Summary Table
        for b in all_block_data:
            empty_count = sum(1 for u in b['units'] if u['count'] == 0)
            status = "OK"
            if b['avg'] < (project_standard * 0.6): status = "UNDER-DOCUMENTED"
            
            print(f"{b['block_name']:<15} | {len(b['units']):<8} | {empty_count:<8} | {b['avg']:<10.2f} | {status}")

        # 4. Detailed Unit-Level Outliers
        print("\nUNIT-LEVEL OUTLIERS (Detailed Folder Analysis):")
        print(f"Project Standard identified as ~{project_standard} photos per unit.\n")
        
        outliers_found = False
        for b in all_block_data:
            for u in b['units']:
                folder_label = f"{b['block_name']} > {u['name']}"
                
                # Logic to catch anomalies
                if u['count'] == 0:
                    print(f" [X] EMPTY FOLDER:   {folder_label}")
                    outliers_found = True
                elif u['count'] > (project_standard * 2.5):
                    print(f" [!] HIGH ANOMALY:   {folder_label} ({u['count']} photos - check for grouped units)")
                    outliers_found = True
                elif 0 < u['count'] < (project_standard * 0.5):
                    print(f" [-] LOW ANOMALY:    {folder_label} ({u['count']} photos - potentially incomplete)")
                    outliers_found = True

        if not outliers_found:
            print(" No anomalies found. All folders match project standards.")
            
        print(f"\n{'='*95}\n")

if __name__ == "__main__":
    validate_with_detailed_outliers()