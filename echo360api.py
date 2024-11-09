from pathlib import Path
from typing import Dict

import requests
from requests import Response
from tqdm import tqdm

enrollments_url = "https://echo360.net.au/user/enrollments"
syllabus_url = "https://echo360.net.au/section/{section_id}/syllabus"
lesson_url = "https://echo360.net.au/lesson/{lesson_id}/classroom"
transcript_url = "https://echo360.net.au/api/ui/echoplayer/lessons/{lesson_id}/medias/{media_id}/transcript"

# Read the cookie
with open("cookie.txt", "r") as f:
    cookie_file = f.read()
    cookie_string = cookie_file.replace("\r", "").replace("\n", "")


def get_request_cookies() -> Dict[str, str]:
    return dict(item.split("=", 1) for item in cookie_string.split("; ") if "=" in item)


def get_request_headers() -> Dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate, br"
    }
    return headers


def fetch(url: str) -> Response:
    response = requests.get(url, headers=get_request_headers(), cookies=get_request_cookies())
    if response.status_code == 200:
        return response
    else:
        raise Exception(f"Failed to fetch data. status_code={response.status_code}  URL={url}")


def fetch_json(url: str):
    return fetch(url).json()


def fetch_text(url: str) -> str:
    return fetch(url).text


def download_file(url: str, path: str) -> None:
    response = requests.get(url, stream=True, headers=get_request_headers(), cookies=get_request_cookies())
    fn = Path(path).name
    if response.status_code == 200:
        total_size = int(response.headers.get('content-length', 0))
        with open(path, "wb") as file:
            for chunk in tqdm(response.iter_content(chunk_size=1024),
                              total=total_size // 1024,
                              unit="KB",
                              desc=f"Downloading {fn}"):
                file.write(chunk)
    else:
        raise Exception(f"Failed to download the file. Status code: {response.status_code}  URL={url}")


def get_enrollments():
    return fetch_json(enrollments_url)["data"]


def get_unit_syllabus(section_id):
    url = syllabus_url.replace("{section_id}", section_id)
    return fetch_json(url)["data"]


def get_lesson_html(lesson_id):
    url = lesson_url.replace("{lesson_id}", lesson_id)
    return fetch_text(url)


def get_transcript(lesson_id, media_id):
    url = transcript_url.replace("{lesson_id}", lesson_id).replace("{media_id}", media_id)
    return fetch_json(url)["data"]
