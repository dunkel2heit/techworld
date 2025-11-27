# run_waitress.py
from waitress import serve
from wsgi import application

if __name__ == '__main__':
    serve(application, listen='*:8000')