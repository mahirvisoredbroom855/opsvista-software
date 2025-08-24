import os

def fix_fact_finance_model():
    """Remove raw_data_id field from FactFinance model"""
    
    models_file = "app/features/finance/models.py"
    
    if not os.path.exists(models_file):
        print("❌ models.py not found!")
        return False
    
    with open(models_file, 'r') as f:
        content = f.read()
    
    # Remove raw_data_id line
    lines = content.split('\n')
    filtered_lines = []
    
    for line in lines:
        # Skip lines that contain raw_data_id
        if 'raw_data_id' not in line:
            filtered_lines.append(line)
        else:
            print(f"🗑️ Removing line: {line.strip()}")
    
    # Write back the cleaned content
    with open(models_file, 'w') as f:
        f.write('\n'.join(filtered_lines))
    
    print("✅ Removed raw_data_id from FactFinance model")
    return True

if __name__ == "__main__":
    fix_fact_finance_model()
