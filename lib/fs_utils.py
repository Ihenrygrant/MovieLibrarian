import os
import re


def next_available_filename(base_path, name, ext):
    full = os.path.join(base_path, f"{name}{ext}")
    counter = 1
    while os.path.exists(full):
        full = os.path.join(base_path, f"{name} ({counter}){ext}")
        counter += 1
    return full