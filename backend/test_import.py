
import sys
from os.path import abspath, dirname
sys.path.insert(0, dirname(abspath(__file__)))
try:
    import app.main
    print("Success: app.main imported")
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Other error: {e}")
    sys.exit(1)
