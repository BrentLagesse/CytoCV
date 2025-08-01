#!/bin/bash

# Start the app using Gunicorn for production
# <module> is the name of the folder that contains wsgi.py
gunicorn --bind=0.0.0.0 --timeout 1200 yeastweb.wsgi
