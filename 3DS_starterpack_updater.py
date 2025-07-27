import sys
import subprocess
import os
import zipfile
import shutil
import requests
import time
import json
import argparse
from datetime import datetime, timedelta

# --- Command-Line Argument Parser ---
parser = argparse.ArgumentParser(description="3DS Starter Pack Updater")
parser.add_argument("--clear-cache", action="store_true", help="Clear the cache file to force API refresh")
args = parser.parse_args()

# --- Dependency Check and Installation ---
try:
    if os.name == 'nt':  # Check if the operating system is Windows
        os.system('title 3DS Starter Pack Updater')
except Exception:
    pass

REQUIRED_PACKAGES = ['requests']

dependencies_ok = True
for package in REQUIRED_PACKAGES:
    try:
        __import__(package)
    except ImportError:
        print(f"'{package}' not found. Attempting to install automatically...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"Successfully installed '{package}'.")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install '{package}': {e}")
            print("Please install it manually by running: pip install " + package)
            dependencies_ok = False
            break
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during installation of '{package}': {e}")
            dependencies_ok = False
            break

if not dependencies_ok:
    print("\nCritical dependencies are missing or failed to install.")
    print("Please resolve the issues above to proceed.")
    input("Press Enter to exit...")
    sys.exit(1)

# --- GitHub Token (Optional) ---
# Check for token once, but only print verbose instructions if needed later
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# --- Cache Configuration ---
CACHE_FILE = "3ds_starter_pack_cache.json"
CACHE_DURATION = timedelta(days=1)  # Cache expires after 1 day

# Define the GitHub repositories and desired filename patterns
REPOSITORIES = {
    "Luma3DS": {
        "owner": "LumaTeam",
        "repo": "Luma3DS",
        "download_filename_patterns": [".zip"],
    },
    "FBI": {
        "owner": "lifehackerhansol",
        "repo": "FBI",
        "download_filename_patterns": [".cia", ".3dsx"],
    },
    "Homebrew Launcher Dummy": {
        "owner": "PabloMK7",
        "repo": "homebrew_launcher_dummy",
        "download_filename_patterns": [".cia", ".3dsx"],
    },
    "Anemone3DS": {
        "owner": "astronautlevel2",
        "repo": "Anemone3DS",
        "download_filename_patterns": [".cia", ".3dsx"],
    },
    "Checkpoint": {
        "owner": "bernardogiordano",
        "repo": "checkpoint",
        "download_filename_patterns": [".cia", ".3dsx"],
    },
    "FTPD": {
        "owner": "mtheall",
        "repo": "ftpd",
        "download_filename_patterns": ["ftpd.cia", "ftpd.3dsx"],
    },
    "Universal-Updater": {
        "owner": "Universal-Team",
        "repo": "Universal-Updater",
        "download_filename_patterns": [".cia", ".3dsx"],
    },
    "GodMode9": {
        "owner": "d0k3",
        "repo": "GodMode9",
        "download_filename_patterns": [".zip"],
    },
}

# --- Main output directory and its standard subfolders ---
DOWNLOAD_DIR = "3DS Starter Pack"
CIAS_SUBDIR_NAME = "cias"
THREEDS_SUBDIR_NAME = "3ds"
LUMA_DIR_NAME = "luma"
PAYLOADS_DIR_NAME = "payloads"

# Full paths for these main output subdirectories
CIAS_FULL_PATH = os.path.join(DOWNLOAD_DIR, CIAS_SUBDIR_NAME)
THREEDS_FULL_PATH = os.path.join(DOWNLOAD_DIR, THREEDS_SUBDIR_NAME)
LUMA_PAYLOADS_FULL_PATH = os.path.join(DOWNLOAD_DIR, LUMA_DIR_NAME, PAYLOADS_DIR_NAME)
GM9_DIR_FULL_PATH = os.path.join(DOWNLOAD_DIR, "gm9") # for GodMode9's gm9 folder

# --- Temporary directory for all initial downloads ---
TEMP_DIR = "temp_downloads_staging"


def load_cache():
    """Load cached release data from file."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                for key, entry in list(cache.items()):
                    if not all(k in entry for k in ["url", "filename", "timestamp", "etag"]):
                        print(f"Invalid cache entry for {key}, ignoring.")
                        del cache[key]
                return cache
    except Exception as e:
        print(f"Error loading cache: {e}")
    return {}

def save_cache(cache):
    """Save release data to cache file."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=4)
        print(f"Updated cache in {CACHE_FILE}")
    except Exception as e:
        print(f"Error saving cache: {e}")

def handle_rate_limit(response, owner, repo):
    """Handle GitHub API rate limit errors by waiting until reset or retry-after."""
    if response.status_code in (403, 429):
        headers = response.headers
        if "x-ratelimit-remaining" in headers and headers["x-ratelimit-remaining"] == "0":
            reset_time = int(headers.get("x-ratelimit-reset", 0))
            if reset_time:
                current_time = int(time.time())
                wait_time = max(reset_time - current_time, 1)
                wib_offset_hours = 7 # Indonesia is WIB, UTC+7
                wib_reset = datetime.utcfromtimestamp(reset_time) + timedelta(hours=wib_offset_hours)
                
                print(f"\n--- GitHub API Rate Limit Exceeded for {owner}/{repo} ---")
                print(f"You have no remaining API calls for this hour.")
                print(f"Please wait {wait_time} seconds (until {wib_reset.strftime('%H:%M:%S WIB')}) to continue.")
                
                # --- NEW: Display token instructions ONLY if needed ---
                if not GITHUB_TOKEN:
                    print("\nFor higher API limits (5000/hour), create a Classic Personal Access Token with 'public_repo' scope:")
                    print("1. Go to https://github.com/settings/tokens")
                    print("2. Click 'Generate new token (classic)'")
                    print("3. Set name, expiration (e.g., 30 days), and select 'public_repo' scope")
                    print("4. Set environment variable:")
                    print("   - Windows: Run `setx GITHUB_TOKEN \"your_token_here\"` in Command Prompt")
                    print("   - macOS/Linux: Add `export GITHUB_TOKEN=\"your_token_here\"` to ~/.bashrc or ~/.zshrc")
                    print("   Then restart this tool.")
                else:
                    print("You are using a GitHub token, but the limit was still hit (likely secondary rate limit or high usage).")
                print("----------------------------------------------------------------------")
                return True, wait_time
        elif "retry-after" in headers:
            wait_time = int(headers.get("retry-after", 60))
            print(f"\n--- GitHub API Secondary Rate Limit for {owner}/{repo} ---")
            print(f"You are being rate limited. Please wait {wait_time} seconds.")
            print("----------------------------------------------------------------------")
            return True, wait_time
    return False, 0

def get_latest_release_asset_url(owner, repo, patterns, cache, retry_count=3):
    """Fetches the latest release, using cache if available."""
    cache_key = f"{owner}/{repo}"
    current_time = datetime.utcnow()
    
    # Check cache
    if not args.clear_cache and cache_key in cache:
        cache_entry = cache[cache_key]
        try:
            cache_time = datetime.fromisoformat(cache_entry["timestamp"])
            if current_time - cache_time < CACHE_DURATION:
                print(f"Using cached data for {owner}/{repo}")
                return cache_entry.get("url"), cache_entry.get("filename")
        except ValueError:
            print(f"Invalid cache timestamp for {owner}/{repo}, fetching new data")

    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github.com.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if cache_key in cache and "etag" in cache[cache_key]:
        headers["If-None-Match"] = cache[cache_key]["etag"]

    for attempt in range(retry_count):
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 304:  # Not Modified
                print(f"No changes for {owner}/{repo}, using cached data")
                return cache[cache_key].get("url"), cache[cache_key].get("filename")
            
            # Handle specific rate limit situation before raising for other errors
            should_wait, wait_time = handle_rate_limit(response, owner, repo)
            if should_wait:
                time.sleep(wait_time + 1) # Add a buffer second
                continue # Retry after waiting

            response.raise_for_status() # Raise for other HTTP errors (4xx, 5xx)
            release_data = response.json()

            assets = release_data.get("assets", [])
            if not assets:
                print(f"No assets found for {owner}/{repo}'s latest release.")
                return None, None

            for pattern in patterns:
                for asset in assets:
                    if asset["name"].lower().endswith(pattern):
                        print(f"Found asset for {owner}/{repo}: {asset['name']}")
                        # Update cache
                        cache[cache_key] = {
                            "url": asset["browser_download_url"],
                            "filename": asset["name"],
                            "timestamp": current_time.isoformat(),
                            "etag": response.headers.get("ETag", "")
                        }
                        save_cache(cache)
                        return asset["browser_download_url"], asset["name"]
            
            print(f"No asset found matching patterns {patterns} for {owner}/{repo}.")
            return None, None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching release for {owner}/{repo}: {e}")
            if attempt < retry_count - 1:
                print(f"Retrying ({attempt + 1}/{retry_count})...")
                time.sleep(2 ** attempt + 1) # Exponential backoff + buffer
            else:
                print(f"Failed after {retry_count} attempts.")
                print(f"Please manually download from https://github.com/{owner}/{repo}/releases")
                return None, None

def download_file(url, filename, download_path):
    """Downloads a file from a given URL to the specified path."""
    try:
        os.makedirs(download_path, exist_ok=True)
        print(f"Downloading {filename} to {download_path} from {url}...")
        headers = {"Accept": "application/octet-stream"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        filepath = os.path.join(download_path, filename)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {filename}")
        return filepath
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {filename}: {e}")
        return None

def main():
    print("╔══════════════════════════════════════════╗")
    print("║        3DS STARTER PACK UPDATER          ║")
    print("╚══════════════════════════════════════════╝")
    print("This tool downloads the latest Luma3DS and")
    print("essential homebrew applications for your 3DS.")
    print("Uses cached data to avoid GitHub API rate limits.")
    print("Run with --clear-cache to force a refresh.")
    print("If errors occur, check the console output for details.")
    print("════════════════════════════════════════════\n")

    input("Press Enter to start the download...")

    print("\nStarting download process...")

    # Clear cache if requested (must be done after welcome and before loading cache)
    if args.clear_cache and os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
            print(f"Cleared cache file: {CACHE_FILE}")
        except Exception as e:
            print(f"Error clearing cache: {e}")

    # Load cache
    cache = load_cache()

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    print(f"Created initial staging directories: '{DOWNLOAD_DIR}/' (final) and '{TEMP_DIR}/' (temporary).")
    
    all_downloaded_items = [] 

    for name, details in REPOSITORIES.items():
        print(f"\n--- Processing {name} ---")
        url, filename = get_latest_release_asset_url(
            details["owner"],
            details["repo"],
            details["download_filename_patterns"],
            cache # Pass cache to the function
        )

        if url and filename:
            temp_filepath = download_file(url, filename, TEMP_DIR)
            
            if temp_filepath:
                is_zip_file = filename.lower().endswith(".zip")
                all_downloaded_items.append((name, filename, temp_filepath, is_zip_file))
            else:
                print(f"Failed to download a suitable asset for {name}.")
                print(f"Manually download from https://github.com/{details['owner']}/{details['repo']}/releases")
        else:
            print(f"Could not find a suitable asset to download for {name}.")
            print(f"Manually download from https://github.com/{details['owner']}/{details['repo']}/releases")

        time.sleep(1) # Delay to avoid secondary rate limits between repo checks

    print("\n--- All downloads complete. Starting file organization and cleanup... ---")

    os.makedirs(CIAS_FULL_PATH, exist_ok=True)
    os.makedirs(THREEDS_FULL_PATH, exist_ok=True)
    os.makedirs(LUMA_PAYLOADS_FULL_PATH, exist_ok=True)
    os.makedirs(os.path.join(DOWNLOAD_DIR, "gm9"), exist_ok=True) # For GodMode9's gm9 folder
    print(f"Created all final destination subdirectories within '{DOWNLOAD_DIR}/'.")

    for name, original_filename, temp_filepath, is_zip_file in all_downloaded_items:
        print(f"\nOrganizing: {original_filename}")
        try:
            if not os.path.exists(temp_filepath): # Check if temp file still exists before processing
                print(f"Skipping {original_filename}: Temporary file not found (might have failed download or already processed).")
                continue

            if is_zip_file:
                with zipfile.ZipFile(temp_filepath, 'r') as zf:
                    if name == "GodMode9":
                        firm_found = False
                        for member in zf.namelist():
                            if os.path.basename(member).lower() == "godmode9.firm":
                                firm_dest_path = os.path.join(LUMA_PAYLOADS_FULL_PATH, "GodMode9.firm")
                                with open(firm_dest_path, 'wb') as outfile:
                                    outfile.write(zf.read(member))
                                print(f"Extracted GodMode9.firm to {LUMA_PAYLOADS_FULL_PATH}")
                                firm_found = True
                            elif "gm9/" in member:
                                zf.extract(member, DOWNLOAD_DIR)
                                print(f"Extracted {member} to {DOWNLOAD_DIR}")
                        if not firm_found:
                            print(f"Warning: GodMode9.firm not found in {original_filename} zip file.")
                    elif name == "Luma3DS":
                        zf.extractall(DOWNLOAD_DIR)
                        print(f"Extracted Luma3DS contents to {DOWNLOAD_DIR} (SD card root).")
                
                os.remove(temp_filepath)
                print(f"Cleaned up temporary zip: {original_filename}")
            else: # Handle non-zip files by moving them
                final_dest_path = DOWNLOAD_DIR # Default to root

                if original_filename.lower().endswith(".cia"):
                    final_dest_path = CIAS_FULL_PATH
                elif original_filename.lower().endswith(".3dsx"):
                    final_dest_path = THREEDS_FULL_PATH

                shutil.move(temp_filepath, os.path.join(final_dest_path, original_filename))
                print(f"Moved '{original_filename}' to '{os.path.basename(final_dest_path)}/' folder.")

        except zipfile.BadZipFile:
            print(f"Error: {original_filename} is not a valid zip file. Skipping extraction and deletion.")
        except Exception as e:
            print(f"Error during organization of {original_filename}: {e}.")
    else:
        print("No files were downloaded for organization.")

    print("\n--- Verifying critical files... ---")
    godmode9_firm_exists = os.path.exists(os.path.join(LUMA_PAYLOADS_FULL_PATH, "GodMode9.firm"))
    luma_boot_firm_exists = os.path.exists(os.path.join(DOWNLOAD_DIR, "boot.firm"))

    if godmode9_firm_exists:
        print("Verification: GodMode9.firm found in luma/payloads/. OK.")
    else:
        print("WARNING: GodMode9.firm NOT FOUND in luma/payloads/. Manual check needed!")

    if luma_boot_firm_exists:
        print("Verification: Luma's boot.firm found in root. OK.")
    else:
        print("WARNING: Luma's boot.firm NOT FOUND in root. Manual check needed!")

    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
            print(f"\nRemoved temporary staging directory: {TEMP_DIR}")
        except Exception as e:
            print(f"ERROR: Could not remove temporary directory {TEMP_DIR}: {e}")

    print("\n════════════════════════════════════════════")
    print("Download and organization complete!         ")
    print("Your '3DS Starter Pack' folder is ready.")
    print("If any downloads failed, check the GitHub release pages listed above.")
    print("To force a refresh, run with --clear-cache or delete '3ds_starter_pack_cache.json'.")
    print("════════════════════════════════════════════")
    input("Press Enter to end...")

if __name__ == "__main__":
    main()