# Echo360 Downloader

Download lecture recordings from your Echo360 account.

## Usage
Copy your browser cookie for Echo360 into `cookie.txt`, and run `downloader.py`.

## Notes
1. `downloader.py` can resume downloading from where it left off.
However, if the script was interrupted while writing the file, you may need to manually delete the partially downloaded file.`
2. The program doesn’t validate the provided cookies.
Not supplying the cookies or supplying invalid/expired ones may lead to unrelated errors
(e.g., a JSON parse error due to API calls being redirected to the login page).
