from app import app as application

# WSGI entry point for production servers (Gunicorn/uWSGI/Waitress)
# Example (gunicorn): gunicorn --workers 4 --bind 0.0.0.0:8000 wsgi:application
