def safe_decimal(self, value):
    """Simple decimal parsing that always works"""
    if value is None or value == "":
        return None
    
    try:
        from decimal import Decimal
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        # Clean string
        clean_value = str(value).replace(',', '').replace(' ', '')
        
        # Extract numbers only
        import re
        numbers_only = re.sub(r'[^\d.-]', '', clean_value)
        
        if numbers_only and numbers_only != '-':
            return Decimal(numbers_only)
        
        return None
        
    except:
        return None
