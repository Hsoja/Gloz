"""Local development server. Never use this in production.

    python run.py            # http://127.0.0.1:5000
"""

import os

from app import create_app

if __name__ == "__main__":
    os.environ.setdefault("GLOZ_ENV", "development")
    # Debug mode stays off: the Werkzeug debugger allows code execution if exposed.
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
