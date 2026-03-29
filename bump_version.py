#!/usr/bin/env python3
"""
Script to bump app version
Usage: python bump_version.py [major|minor|patch]
"""

import sys
import re

def bump_version(version, bump_type):
    parts = version.split('.')
    if bump_type == 'major':
        parts[0] = str(int(parts[0]) + 1)
        parts[1] = '0'
        parts[2] = '0'
    elif bump_type == 'minor':
        parts[1] = str(int(parts[1]) + 1)
        parts[2] = '0'
    elif bump_type == 'patch':
        parts[2] = str(int(parts[2]) + 1)
    return '.'.join(parts)

# Read current version
with open('VERSION', 'r') as f:
    current_version = f.read().strip()

# Get bump type
bump_type = sys.argv[1] if len(sys.argv) > 1 else 'patch'

# Bump version
new_version = bump_version(current_version, bump_type)

# Write new version
with open('VERSION', 'w') as f:
    f.write(new_version)

print(f"Version bumped: {current_version} → {new_version}")
