import os
import subprocess
import sys

# validate metadata only (fast) or validate by actually trying to decode the video
METADATA_ONLY = False

# enable hardware acceleration. takes effect only if METADATA_ONLY==False
HARDWARE_ACCELERATION = False

def get_file_size_mb(filepath):
    size_bytes = os.path.getsize(filepath)
    return round(size_bytes / (1024 * 1024), 2)  # size in MB with 2 decimals


def is_valid_mp4_metadata(filepath):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries',
             'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking {filepath}: {e}")
        return False

def is_valid_mp4_full(filepath):
    try:
        result = subprocess.run(
            (
                ['ffmpeg', '-v', 'error', '-hwaccel', 'auto', '-i', filepath, '-f', 'null', '-']
                if HARDWARE_ACCELERATION else
                ['ffmpeg', '-v', 'error', '-i', filepath, '-f', 'null', '-']
            ),
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking {filepath}: {e}")
        return False

def is_valid_mp4(filepath):
    if METADATA_ONLY:
        return is_valid_mp4_metadata(filepath)
    else:
        return is_valid_mp4_full(filepath)

def validate_mp4s(root_dir):
    invalid_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for file in filenames:
            if file.lower().endswith('.mp4'):
                full_path = os.path.join(dirpath, file)
                size_mb = get_file_size_mb(full_path)
                print(f"Validating: {full_path} ({size_mb} MB)")
                if not is_valid_mp4(full_path):
                    print(f"❌ Invalid MP4: {full_path}")
                    invalid_files.append(full_path)
    return invalid_files

if __name__ == "__main__":
    from downloader import base_dir
    directory = base_dir
    invalids = validate_mp4s(directory)
    print("\nSummary:")
    if invalids:
        print("Invalid MP4 files found:")
        for f in invalids:
            print(f)
    else:
        print("All MP4 files are valid.")
