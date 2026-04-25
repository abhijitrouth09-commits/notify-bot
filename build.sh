#!/usr/bin/env bash

pip install -r requirements.txt

# 🔥 install browsers + dependencies
playwright install --with-deps chromium
