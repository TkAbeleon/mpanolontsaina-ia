#!/usr/bin/env python3
"""Explore the mistralai package structure."""
import os
import sys

# List what's in the mistralai directory
import mistralai
print("mistralai path:", mistralai.__file__)
print("\nmistralai contents:", dir(mistralai))

# Check what's in mistralai/__init__.py
with open(mistralai.__file__, "r") as f:
    print("\nmistralai __init__.py content:\n", f.read())

# Check mistralai/client
try:
    import mistralai.client
    print("\nmistralai.client contents:", dir(mistralai.client))
    with open(os.path.join(os.path.dirname(mistralai.__file__), "client.py"), "r") as f:
        print("\nclient.py content (first 100 lines):\n", f.read(2000))
except ImportError as e:
    print("\nNo mistralai.client:", e)
