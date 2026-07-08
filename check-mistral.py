#!/usr/bin/env python3
"""Vérifie la structure du package mistralai."""
import mistralai
print("mistralai package contents:", dir(mistralai))
import pkg_resources
print("mistralai version:", pkg_resources.get_distribution("mistralai").version)
