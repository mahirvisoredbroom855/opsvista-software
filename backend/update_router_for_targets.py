import os

def update_router_for_target_files():
    """Update router.py to only process target files"""
    
    router_file = "app/features/finance/router.py"
    
    if not os.path.exists(router_file):
        print("❌ router.py not found!")
        return False
    
    # Read the current router file
    with open(router_file, 'r') as f:
        content = f.read()
    
    # Replace list_excel_files with list_target_finance_files
    updated_content = content.replace(
        'list_excel_files(',
        'list_target_finance_files('
    )
    
    # Also update any comments that mention listing all files
    updated_content = updated_content.replace(
        'List all Excel files',
        'List target finance files only'
    )
    
    # Write the updated content back
    with open(router_file, 'w') as f:
        f.write(updated_content)
    
    print("✅ Updated router.py to use target files only")
    return True

if __name__ == "__main__":
    update_router_for_target_files()
