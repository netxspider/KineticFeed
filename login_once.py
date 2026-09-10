"""
Kinetic Feed - Legacy Instagram Login Entrypoint
Forwards to login_instagram.py for consistent session persistence.
"""

from login_instagram import save_instagram_session

if __name__ == "__main__":
    save_instagram_session()