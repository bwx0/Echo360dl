import json
import pathlib
import re


def collapse_int_arrays(json_text: str):
    pattern = r'\[\s*(?:\d+\s*,\s*)*\d+\s*]'

    def remove_spaces(match):
        return re.sub(r'[.\s]+', ' ', match.group(), flags=re.S)

    new_text = re.sub(pattern, remove_spaces, json_text)
    return new_text


def write_json(path: str, obj):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json_str = json.dumps(obj, indent=4)
        json_str = collapse_int_arrays(json_str)
        f.write(json_str)


def write_file(path: str, text: str):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def read_json(path: str):
    with open(path, "r") as f:
        return json.load(f)


def file_exists(path: str):
    return pathlib.Path(path).exists()


def check_exists(path: str):
    if file_exists(path):
        return True
    print(f"File does not exist: {path}")
    return False


def replace_non_alphanumeric(s: str):
    result = re.sub(r'[^a-zA-Z0-9]', '_', s)
    result = re.sub(r'_+', '_', result)
    return result


def ms_to_srt_time(ms: int):
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    milliseconds = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
