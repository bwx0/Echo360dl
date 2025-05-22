import os
import re
import json
import pathlib
import subprocess
import sys
from traceback import print_exc
from typing import Any, Tuple, List

import echo360api as api
from util import write_json, read_json, check_exists, replace_non_alphanumeric, write_file, ms_to_srt_time, \
    file_exists

"""
elrollments.json
  |--metadata_unit1(CITSxxxx)
  |    |--lecture1_metadata
  |    |    |--media_audio_quality_x_metadata
  |    |    |--media_video_quality_x_metadata
  |    |    ...
  |    |--lecture2_metadata
  |    ...
  |----metadata_unit2(CITSxxxx)
  ...
"""

# base_dir = "E:\\Echo360"
base_dir = "data"

enrollments_json = base_dir + "/enrollments.json"
syllabus_json = base_dir + "/unit_data/{code} {course_name}.json"
lesson_json = base_dir + "/lesson_data/{course_name}.json"
raw_transcript_dir = base_dir + "/transcript_data/{course_name}/{lesson_name}.json"
videos_dir = base_dir + "/videos/{course_name}/{lesson_name}.mp4"
transcript_dir = base_dir + "/videos/{course_name}/{lesson_name}.srt"

pathlib.Path(base_dir).mkdir(parents=True, exist_ok=True)
pathlib.Path(syllabus_json).parent.mkdir(parents=True, exist_ok=True)
pathlib.Path(lesson_json).parent.mkdir(parents=True, exist_ok=True)


def syllabus_json_path(unit_obj):
    return syllabus_json.replace("{code}", unit_obj["courseCode"]).replace("{course_name}", unit_obj["courseName"])


def lesson_json_path(unit_name):
    return lesson_json.replace("{course_name}", unit_name)


def fetch_enrollments():
    """
    Fetch metadata of a list of enrolled units.
    It contains a list of enrolled units and their metadata (e.g. unit ID).
    """
    # Fetch the latest enrollments.json.
    # The file shouldn't be large so fetch it every time we run the script.

    # if pathlib.Path(enrollments_json).exists():
    #     print("enrollments.json already exists.")
    #     return

    print("Fetching enrollments.json")
    syllabus = api.get_enrollments()
    write_json(enrollments_json, syllabus)


def _fetch_syllabus(unit_obj):
    """
    Fetch metadata for a unit.
    Syllabus contains detailed info about each unit, including a list of
    lectures and their metadata (e.g. lecture ids).
    :param unit_obj:
    """
    out_path = syllabus_json_path(unit_obj)
    if pathlib.Path(out_path).exists():
        print(f"{out_path} already exists.")
        return

    print(f"Fetching metadata for {unit_obj['courseName']}")
    syllabus = api.get_unit_syllabus(unit_obj["sectionId"])
    write_json(out_path, syllabus)


def fetch_unit_metadata():
    """
    Fetch metadata for each unit in the list of enrolled units.
    """
    if not check_exists(enrollments_json):
        return

    enrollments = read_json(enrollments_json)

    units = enrollments[0]["userSections"]
    for unit in units:
        _fetch_syllabus(unit)


def _fetch_lecture_video_info(lesson):
    """
    Fetch metadata of one lecture, including video urls for this lecture.
    :param lesson:
    :return:
    """
    name = lesson["name"]
    lesson_id = lesson["id"]
    print(name)

    lesson_html = api.get_lesson_html(lesson_id)
    json_data = None
    keyword = 'Echo["echoPlayerV2FullApp"]'
    for line in lesson_html.splitlines():
        ln = line.strip()
        if ln.startswith(keyword):
            json_data = ln[len(keyword) + 2:-3]
            break
    json_data = json_data.replace("\\/", "/").encode().decode('unicode_escape')
    lesson_data = json.loads(json_data)
    return lesson_data


def fetch_video_info():
    """
    Fetch media metadata of each lesson of each unit, including video urls of each lecture.
    """
    if not check_exists(enrollments_json):
        return

    enrollments = read_json(enrollments_json)

    units = enrollments[0]["userSections"]
    for unit in units:
        course_name = unit["courseName"]
        path = lesson_json_path(course_name)
        if file_exists(path):
            print(f"Lecture metadata already exists for {course_name}.")
            continue

        print(f"Fetching lecture metadata for {course_name}")
        syllabus_path = syllabus_json_path(unit)
        if not check_exists(syllabus_path):
            continue
        metadata = read_json(syllabus_path)

        lectures = []
        for obj in metadata:
            if "groupInfo" in obj:
                print(f">>>>>> [WARNING] <<<<<<< grouped lectures: {obj['groupInfo']['name']}")
                continue
            lesson = obj["lesson"]["lesson"]
            lecture_info = _fetch_lecture_video_info(lesson)
            lectures.append(lecture_info)

        write_json(path, lectures)


def _save_transcript_as_srt(transcript_data, course_name, lesson_name):
    file_name = replace_non_alphanumeric(lesson_name)
    path = transcript_dir.replace("{course_name}", course_name).replace("{lesson_name}", file_name)

    srt_content = ""
    for i, cue in enumerate(transcript_data["contentJSON"]["cues"], start=1):
        start_time = ms_to_srt_time(cue["startMs"])
        end_time = ms_to_srt_time(cue["endMs"])
        content = cue["content"]

        srt_content += f"{i}\n{start_time} --> {end_time}\n{content}\n\n"

    write_file(path, srt_content)


def download_transcript(lesson):
    """
    Download transcript for a lesson.
    """
    course_name = lesson["sectionInfo"]["course"]["courseName"]
    lesson_name = lesson["lesson"]["name"]
    file_name = replace_non_alphanumeric(lesson_name)
    if file_exists(transcript_dir.replace("{course_name}", course_name).replace("{lesson_name}", file_name)):
        print(f"Transcript already exists for {lesson_name}")
        return
    print(f"Fetching transcript for {lesson_name}")

    lesson_id = lesson["lesson"]["id"]
    video_data = lesson["video"]
    media_id = video_data["mediaId"]
    transcript_data = api.get_transcript(lesson_id, media_id)

    path = raw_transcript_dir.replace("{course_name}", course_name).replace("{lesson_name}", file_name)
    write_json(path, transcript_data)
    _save_transcript_as_srt(transcript_data, course_name, lesson_name)

    return transcript_data


def _ensure_video_dir(course_name, lesson_name):
    file_name = replace_non_alphanumeric(lesson_name)
    out_vid_path = videos_dir.replace("{course_name}", course_name).replace("{lesson_name}", file_name)
    pathlib.Path(out_vid_path).parent.mkdir(parents=True, exist_ok=True)
    return out_vid_path


def _merge_tracks_and_save(audio_path, video_path, course_name, lesson_name):
    out_vid_path = _ensure_video_dir(course_name, lesson_name)

    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",
        out_vid_path
    ]
    try:
        subprocess.run(command, check=True)
        print(f"Files merged successfully into {out_vid_path}")
    except subprocess.CalledProcessError:
        print("An error occurred while merging the files.")


def download_lesson_video(lesson):
    """
    Lecture metadata contains only urls of m3u8 files, which are textual files containing
    links to other m3u8 files or m4s files. This method finds urls of the ultimate playable
    audios & videos (usually in the form of m4s files) and then merge them into one single file
    and save as .mp4 using ffmpeg.
    """
    lesson_name = lesson["lesson"]["name"]
    file_name = replace_non_alphanumeric(lesson_name)
    course_name = lesson["sectionInfo"]["course"]["courseName"]

    # Check if the video already exists.
    if file_exists(videos_dir.replace("{course_name}", course_name).replace("{lesson_name}", file_name)):
        print(f"Video already exists for {lesson_name}")
        return
    print(f"Fetching video for {lesson_name}")

    playableMedias = lesson["video"]["playableMedias"]
    targets: List[Tuple[Any, int, str]] = []  # (obj, max_quality, track_type)
    track_found = set()
    full_video_url = None
    fallback_to_full_video = False

    # Find the media file that contains either video track or audio track.
    # Media that claims to have both does not actually have both.
    for media in playableMedias:
        trackType = media["trackType"]
        quality = media["quality"]
        max_quality = max(quality)
        track_type = trackType[0].lower()
        if len(trackType) == 1 and track_type not in track_found:
            targets.append((media, max_quality, track_type))  # Keep the one of best quality
            track_found.add(track_type)
        if len(trackType) == 2 and full_video_url is None:
            full_video_url = media["uri"]

    if full_video_url is None:
        assert len(targets) == 2, "Expect 2 m4s files (audio and video track respectively)"
        assert "audio" in track_found and "video" in track_found, "Expect both audio and video tracks"
    elif len(targets) != 2:
        targets = []
        fallback_to_full_video = True

    # For each of the audio and video track, save them as a tmp file.
    for media, max_quality, track_type in targets:
        url = media["uri"]
        m3u8_source = api.fetch_text(url)  # url is a link to a first level m3u8 file.
        url_parts = re.split(r"(/)", url)  # split the url into parts so we can make upcoming relative urls absolute.

        # Fetch all m3u8 files referenced by the first level m3u8 file
        second_level_m3u8 = None
        for line in m3u8_source.splitlines():
            line = line.strip()
            # Find the line that contains the url of the audio/video of the desired quality
            if line.endswith(".m3u8") and f"q{max_quality}" in line:
                url_parts[-1] = line
                url2 = ''.join(url_parts)
                second_level_m3u8 = url2

        assert second_level_m3u8 is not None, f"audio/video of the desired quality {max_quality} not found"

        # The second level m3u8 file contains the relative link to a m4s file. Extract that link.
        m2_source = api.fetch_text(second_level_m3u8)
        m4s_list = list(set([line for line in m2_source.splitlines() if line.endswith(".m4s")]))
        if len(m4s_list) > 0:  # old version
            assert len(m4s_list) == 1, f"Expect 1 m4s file within an m3u8 file, got {len(m4s_list)}"

            # Combine the relative link with the base url to get the full url of the m4s file.
            url_parts[-1] = m4s_list[0]
            url_ultimate = ''.join(url_parts)

            # Save the audio/video track as a tmp m4s file.
            print("URL: " + url_ultimate)
            api.download_file(url_ultimate, f"{track_type}.tmp.m4s")
        else:
            print("m3u8 file contains no m4s files. Falling back to full video download.")
            fallback_to_full_video = True
            break

    if fallback_to_full_video:
        out_vid_path = _ensure_video_dir(course_name, lesson_name)
        command = [
            "ffmpeg",
            '-loglevel', 'warning',  # suppress output
            '-headers', ''.join(f'{k}: {v}\r\n' for k, v in api.get_request_headers_with_cookie().items()),
            "-i", full_video_url,
            "-c", "copy",
            out_vid_path
        ]
        try:
            subprocess.run(command, check=True)
            print(f"Video saved successfully as {out_vid_path}")
        except subprocess.CalledProcessError:
            print("An error occurred while saving the video.")
        return

    # Now we have m4s files for audio and video tracks. Merge them and save to the video folder.
    _merge_tracks_and_save("audio.tmp.m4s", "video.tmp.m4s", course_name, lesson_name)
    os.remove("audio.tmp.m4s")
    os.remove("video.tmp.m4s")


def fetch_videos():
    """
    Download audio & video tracks and merge into a single .mp4 file for each lecture of each unit.
    Also download the subtitles and save as .srt files.
    :return:
    """
    if not check_exists(enrollments_json):
        return
    enrollments = read_json(enrollments_json)
    units = enrollments[0]["userSections"]
    for unit in units:  # For each unit
        course_name = unit["courseName"]
        lesson_data = read_json(lesson_json_path(course_name))
        print(f"{'=' * 50}\n{course_name}\n{'=' * 50}")

        for lesson in lesson_data:  # For each lecture in that unit
            if lesson["video"] is None:
                print(f">>>>>>>>>> WARNING: No content in lesson {lesson['lesson']['name']}")
                continue
            download_transcript(lesson)
            try:
                download_lesson_video(lesson)
            except Exception:
                sys.stdout.flush()
                print_exc(file=sys.stderr)
                sys.stderr.flush()


def fetch_all():
    # Fetch enrollments at the beginning, which contains a list units.
    fetch_enrollments()

    # For each of the unit, fetch metadata for it, which contains a list of lectures.
    fetch_unit_metadata()

    # For each lecture, fetch metadata for it, which contains a list of videos (audio/video from different sources).
    fetch_video_info()

    # For each lecture, download the audio/video and merge into a single .mp4 file.
    fetch_videos()


if __name__ == '__main__':
    fetch_all()
