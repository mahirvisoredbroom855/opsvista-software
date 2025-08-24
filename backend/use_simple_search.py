import os

def update_services_for_simple_search():
    """Update all services to use simple list_target_finance_files method"""
    
    files_to_update = [
        "app/features/finance/finance_sync_service.py",
        "app/features/finance/router.py"
    ]
    
    for file_path in files_to_update:
        if not os.path.exists(file_path):
            print(f"ℹ️ {file_path} not found, skipping")
            continue
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Replace any recursive method calls with simple ones
        updated_content = content.replace(
            'find_target_files_anywhere(',
            'list_target_finance_files('
        )
        
        updated_content = updated_content.replace(
            'list_target_finance_files_recursive(',
            'list_target_finance_files('
        )
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated {file_path} to use simple search")
    
    return True

if __name__ == "__main__":
    update_services_for_simple_search()
