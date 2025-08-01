#!/bin/bash
cd yeastweb
apt-get install -y libgl1-mesa-glx
python manage.py runserver
