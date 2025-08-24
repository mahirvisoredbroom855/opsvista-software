# compatibility shim so 'from backend.app...' resolves to this 'app' package
import sys, types
if 'backend' not in sys.modules:
    m = types.ModuleType('backend')
    import app as _app
    m.app = _app
    sys.modules['backend'] = m
