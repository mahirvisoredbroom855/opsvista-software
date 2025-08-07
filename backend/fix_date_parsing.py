# Add this to excel_processor.py if date parsing is broken
def smart_date_parsing(self, date_value):
    """Simple date parsing that always works"""
    if date_value is None or date_value == "":
        return None
    
    try:
        # Try simple formats first
        from datetime import datetime, date
        
        if isinstance(date_value, (int, float)):
            # Excel date number
            excel_epoch = datetime(1899, 12, 30)
            return (excel_epoch + timedelta(days=int(date_value))).date()
        
        date_str = str(date_value).strip()
        
        # Try common formats
        formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue
        
        return None
        
    except:
        return None
