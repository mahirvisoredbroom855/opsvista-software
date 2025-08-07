import os

def revert_to_simple_search():
    """Revert GoogleDriveService back to simple main folder search"""
    
    service_file = "app/features/finance/google_drive_service.py"
    
    if not os.path.exists(service_file):
        print("❌ google_drive_service.py not found!")
        return False
    
    # Read current file
    with open(service_file, 'r') as f:
        content = f.read()
    
    # Remove the recursive methods by finding and removing them
    lines = content.split('\n')
    
    # Remove lines between recursive method definitions
    filtered_lines = []
    skip_mode = False
    
    for line in lines:
        # Start skipping when we hit recursive method definitions
        if 'def list_target_finance_files_recursive' in line or \
           'def _get_all_subfolders' in line or \
           'def _search_folder_for_targets' in line or \
           'def find_target_files_anywhere' in line:
            skip_mode = True
            continue
        
        # Stop skipping when we hit the next method or end of class
        if skip_mode and (line.strip().startswith('def ') or line.strip() == 'EOF'):
            skip_mode = False
            if line.strip() == 'EOF':
                filtered_lines.append(line)
                continue
        
        # Only add lines when not in skip mode
        if not skip_mode:
            filtered_lines.append(line)
    
    # Write the cleaned content back
    with open(service_file, 'w') as f:
        f.write('\n'.join(filtered_lines))
    
    print("✅ Removed recursive search methods from GoogleDriveService")
    return True

if __name__ == "__main__":
    revert_to_simple_search()



