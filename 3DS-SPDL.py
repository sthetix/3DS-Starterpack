#!/usr/bin/env python3
"""
3DS Starter Pack Updater GUI v2.0.0
A graphical tool to download and organize files for 3DS custom firmware.
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import * # NOSONAR
from tkinter import messagebox, scrolledtext
import json
import os
import sys
import shutil
import requests
import zipfile
import time
import threading
from tkinter import filedialog
from datetime import datetime, timedelta

# --- Script Constants ---
VERSION = "2.0.0"
CONFIG_FILE = 'gui_updater_config.json'
CACHE_FILE = "3ds_starter_pack_cache.json"
CACHE_DURATION = timedelta(days=1)

# --- GitHub repositories and desired filename patterns ---
REPOSITORIES = {
    "Luma3DS": {
        "owner": "LumaTeam",
        "repo": "Luma3DS",
        "download_filename_patterns": [".zip"],
    },
    "GodMode9": {
        "owner": "d0k3",
        "repo": "GodMode9",
        "download_filename_patterns": [".zip"],
    },
    "Finalize": {
        "owner": "hacks-guide",
        "repo": "finalize",
        "download_filename_patterns": ["x_finalize_helper.firm", "finalize.romfs"],
    },
}

# --- Main output directory and its standard subfolders ---
DOWNLOAD_DIR = "3DS Starter Pack"
LUMA_DIR_NAME = "luma"
PAYLOADS_DIR_NAME = "payloads"
LUMA_PAYLOADS_FULL_PATH = os.path.join(DOWNLOAD_DIR, LUMA_DIR_NAME, PAYLOADS_DIR_NAME)
GM9_DIR_FULL_PATH = os.path.join(DOWNLOAD_DIR, "gm9")
TEMP_DIR = "temp_zip_downloads"


class ThreeDSUpdaterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"3DS Starter Pack Downloader v{VERSION}") # NOSONAR
        self.root.geometry("770x650")
        self.root.resizable(True, True)

        # --- Variables ---
        self.github_pat = ttk.StringVar()
        self.config_data = {}
        self.cache_data = {}
        self.output_dir_var = ttk.StringVar()
        self.is_running = False

        self.create_menu()
        self.load_config()
        self.create_main_ui()

        self.log_message("Welcome to the 3DS Starter Pack Downloader!")
        self.log_message(f"Staging folder is '{DOWNLOAD_DIR}'.")
        self.log_message("Click 'Start Update' to begin.")

    def load_config(self):
        """Load config.json and apply settings."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                pat = self.config_data.get('github_pat')
                if pat:
                    self.github_pat.set(pat)
                output_dir = self.config_data.get('output_dir')
                if output_dir and os.path.isdir(output_dir):
                    self.github_pat.set(pat)
        except (json.JSONDecodeError, IOError) as e:
            messagebox.showerror("Config Error", f"Failed to load {CONFIG_FILE}:\n{e}")
            self.config_data = {}

    def save_config(self):
        """Save current config to config.json."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
        except IOError as e:
            self.show_custom_info("Error", f"Failed to save {CONFIG_FILE}:\n{e}", width=450)

    def create_menu(self):
        """Create the top menu bar."""
        menubar = ttk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = ttk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Settings menu
        settings_menu = ttk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="GitHub PAT...", command=self.show_pat_settings)

    def create_main_ui(self):
        """Create the main user interface."""
        # --- Controls Frame ---
        controls_frame = ttk.Labelframe(self.root, text="Controls", padding=10)
        controls_frame.pack(fill=X, padx=10, pady=10)

        self.start_btn = ttk.Button(controls_frame, text="Start Download", bootstyle="success", command=self.run_update_in_thread, width=15)
        self.start_btn.pack(side=LEFT, padx=5)

        self.output_dir_btn = ttk.Button(controls_frame, text="Set Output Directory...", bootstyle="info-outline", command=self.select_output_directory)
        self.output_dir_btn.pack(side=LEFT, padx=5)

        self.clear_cache_btn = ttk.Button(controls_frame, text="Clear Cache", bootstyle="info-outline", command=self.clear_cache)
        self.clear_cache_btn.pack(side=LEFT, padx=5)
        
        # --- Output Path Frame ---
        output_frame = ttk.Labelframe(self.root, text="Output Destination", padding=10)
        output_frame.pack(fill=X, padx=10, pady=(0, 10))

        output_path_label = ttk.Label(output_frame, text="Path:", font=('Segoe UI', 9, 'bold'))
        output_path_label.pack(side=LEFT, padx=(0, 5))
        self.output_path_display = ttk.Label(output_frame, textvariable=self.output_dir_var, font=('Segoe UI', 9), wraplength=550)
        self.output_path_display.pack(side=LEFT, fill=X, expand=True)

        # --- Progress Frame ---
        progress_frame = ttk.Labelframe(self.root, text="Progress", padding=10)
        progress_frame.pack(fill=X, padx=10, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', bootstyle="success-striped")
        self.progress_bar.pack(fill=X, expand=True, side=TOP)
        self.progress_label = ttk.Label(progress_frame, text="", font=('Segoe UI', 8))
        self.progress_label.pack(side=TOP, anchor=W, pady=(5,0))

        self.status_label = ttk.Label(progress_frame, text="Status: Ready", font=('Segoe UI', 9))
        self.status_label.pack(side=TOP, anchor=W, pady=(5,0))

        # --- Log Output Frame ---
        log_frame = ttk.Labelframe(self.root, text="Log Output", padding=10)
        log_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=WORD, font=("Consolas", 9), state=DISABLED)
        self.log_text.pack(fill=BOTH, expand=True)

    # --- UI Update Methods (Thread-safe) ---
    def log_message(self, message):
        def _log():
            self.log_text.config(state=NORMAL)
            self.log_text.insert(END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see(END)
            self.log_text.config(state=DISABLED)
        self.root.after(0, _log)

    def update_status(self, text):
        self.root.after(0, lambda: self.status_label.config(text=f"Status: {text}"))

    def update_progress(self, value, text=""):
        self.root.after(0, lambda: [
            self.progress_bar.config(value=value),
            self.progress_label.config(text=text)
        ])
    
    def set_controls_state(self, state):
        """Enable or disable control buttons. state can be NORMAL or DISABLED."""
        self.root.after(0, lambda: [
            self.start_btn.config(state=state),
            self.clear_cache_btn.config(state=state),
            self.output_dir_btn.config(state=state)
        ])

    # --- Core Logic Methods ---
    def run_update_in_thread(self):
        """Starts the update process in a separate thread to keep the GUI responsive."""
        if self.is_running:
            return
        self.is_running = True
        self.set_controls_state(DISABLED)
        self.update_progress(0, "") # Reset progress bar
        
        # Clear log
        self.log_text.config(state=NORMAL)
        self.log_text.delete(1.0, END)
        self.log_text.config(state=DISABLED)

        update_thread = threading.Thread(target=self.start_update_process, daemon=True)
        update_thread.start()

    def start_update_process(self):
        """The main logic for downloading and organizing files."""
        try:
            self.log_message("Starting update process...")
            self.update_status("Loading cache...")
            
            self.cache_data = self._load_cache()
            
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            os.makedirs(TEMP_DIR, exist_ok=True)
            self.log_message(f"Created staging directories: '{DOWNLOAD_DIR}/' and '{TEMP_DIR}/'.")

            all_downloaded_items = []

            for name, details in REPOSITORIES.items():
                self.log_message(f"\n--- Processing {name} ---")
                self.update_status(f"Fetching info for {name}...")
                urls, filenames = self._get_latest_release_asset_urls(
                    details["owner"], details["repo"], details["download_filename_patterns"]
                )

                if urls and filenames:
                    for url, filename in zip(urls, filenames):
                        self.update_status(f"Downloading {filename}...")
                        temp_filepath = self._download_file(url, filename, TEMP_DIR)
                        if temp_filepath:
                            is_zip_file = filename.lower().endswith(".zip")
                            all_downloaded_items.append((name, filename, temp_filepath, is_zip_file))
                        else:
                            self.log_message(f"ERROR: Failed to download {filename} for {name}.")
                            self.log_message(f"Manually download from https://github.com/{details['owner']}/{details['repo']}/releases")
                else:
                    self.log_message(f"Could not find suitable assets to download for {name}.")
                    self.log_message(f"Manually download from https://github.com/{details['owner']}/{details['repo']}/releases")
                time.sleep(1)

            # --- File Organization ---
            self.log_message("\n--- All downloads complete. Organizing files... ---")
            self.update_status("Organizing files...")
            os.makedirs(LUMA_PAYLOADS_FULL_PATH, exist_ok=True)
            os.makedirs(GM9_DIR_FULL_PATH, exist_ok=True)

            for name, original_filename, temp_filepath, is_zip_file in all_downloaded_items:
                self._organize_file(name, original_filename, temp_filepath, is_zip_file)

            # --- Verification and Cleanup ---
            self.log_message("\n--- Verifying critical files... ---")
            self._verify_files()
            
            if os.path.exists(TEMP_DIR):
                try:
                    shutil.rmtree(TEMP_DIR)
                    self.log_message(f"\nRemoved temporary directory: {TEMP_DIR}")
                except Exception as e:
                    self.log_message(f"ERROR: Could not remove temporary directory {TEMP_DIR}: {e}")
            
            # --- Final Copy to Destination ---
            self._copy_to_destination()

            self.log_message("\n════════════════════════════════════════════")
            self.log_message("Update and organization complete!")
            if not self.output_dir_var.get():
                self.log_message(f"The '{DOWNLOAD_DIR}' folder is ready.")
                self.log_message("Copy its contents to the root of your SD card.")
            self.update_status("Complete!")
            
            
        except Exception as e:
            self.log_message(f"\nFATAL ERROR: An unexpected error occurred: {e}")
            self.update_status("Error!")
        finally:
            self.is_running = False
            self.set_controls_state(NORMAL)
            
    def select_output_directory(self):
        """Open a dialog to select the final output directory."""
        directory = filedialog.askdirectory(title="Select Output Directory (e.g., your SD card root)")
        if directory:
            self.output_dir_var.set(directory)
            self.config_data['output_dir'] = directory
            self.save_config()
            self.log_message(f"Output directory set to: {directory}")

    def _load_cache(self):
        """Load cached release data from file."""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log_message(f"Error loading cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save release data to cache file."""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache_data, f, indent=4)
            self.log_message(f"Updated cache in {CACHE_FILE}")
        except Exception as e:
            self.log_message(f"Error saving cache: {e}")
    
    def clear_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
                self.cache_data = {}
                self.log_message(f"Cache file '{CACHE_FILE}' cleared successfully.")
                self.show_custom_info("Success", f"Cache file '{CACHE_FILE}' has been cleared.", width=400)
            except OSError as e:
                self.log_message(f"Error clearing cache: {e}")
                self.show_custom_info("Error", f"Failed to clear cache:\n{e}", width=400)
        else:
            self.log_message("No cache file to clear.")
            self.show_custom_info("Info", "No cache file found to clear.", width=350)

    def _get_latest_release_asset_urls(self, owner, repo, patterns, retry_count=3):
        """Fetches all matching assets from the latest release, using cache if available."""
        cache_key = f"{owner}/{repo}"
        current_time = datetime.utcnow()
        
        if cache_key in self.cache_data:
            cache_entry = self.cache_data[cache_key]
            try:
                cache_time = datetime.fromisoformat(cache_entry["timestamp"])
                if current_time - cache_time < CACHE_DURATION:
                    self.log_message(f"Using cached data for {owner}/{repo}")
                    return cache_entry.get("urls", []), cache_entry.get("filenames", [])
            except ValueError:
                self.log_message(f"Invalid cache timestamp for {owner}/{repo}, fetching new data")

        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        headers = {"Accept": "application/vnd.github.com.v3+json"}
        token = self.github_pat.get()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if cache_key in self.cache_data and "etag" in self.cache_data[cache_key]:
            headers["If-None-Match"] = self.cache_data[cache_key]["etag"]
        
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 304:
                self.log_message(f"No changes for {owner}/{repo} (ETag match), using cached data.")
                return self.cache_data[cache_key].get("urls", []), self.cache_data[cache_key].get("filenames", [])

            response.raise_for_status()
            release_data = response.json()
            assets = release_data.get("assets", [])
            
            urls, filenames = [], []
            for pattern in patterns:
                for asset in assets:
                    if asset["name"].lower().endswith(pattern.lower()):
                        self.log_message(f"Found asset for {owner}/{repo}: {asset['name']}")
                        urls.append(asset["browser_download_url"])
                        filenames.append(asset["name"])
            
            if urls:
                self.cache_data[cache_key] = {
                    "urls": urls,
                    "filenames": filenames,
                    "timestamp": current_time.isoformat(),
                    "etag": response.headers.get("ETag", "")
                }
                self._save_cache()
                return urls, filenames
            else:
                self.log_message(f"No asset found matching patterns {patterns} for {owner}/{repo}.")
                return [], []

        except requests.exceptions.RequestException as e:
            self.log_message(f"ERROR fetching release for {owner}/{repo}: {e}")
            return [], []

    def _download_file(self, url, filename, download_path):
        """Downloads a file, updating the GUI with progress."""
        try:
            self.log_message(f"Downloading {filename}...")
            headers = {"Accept": "application/octet-stream"}
            token = self.github_pat.get()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            filepath = os.path.join(download_path, filename)
            downloaded_size = 0

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        progress_text = f"{filename} - {downloaded_size/1024/1024:.2f} MB / {total_size/1024/1024:.2f} MB"
                        self.update_progress(progress, progress_text)
            
            self.log_message(f"Successfully downloaded {filename}")
            return filepath
        except requests.exceptions.RequestException as e:
            self.log_message(f"Error downloading {filename}: {e}")
            return None

    def _organize_file(self, name, original_filename, temp_filepath, is_zip_file):
        """Organizes a single downloaded file."""
        self.log_message(f"Organizing: {original_filename}")
        try:
            if not os.path.exists(temp_filepath):
                self.log_message(f"Skipping {original_filename}: Temporary file not found.")
                return

            if is_zip_file:
                with zipfile.ZipFile(temp_filepath, 'r') as zf:
                    if name == "GodMode9":
                        for member in zf.namelist():
                            if os.path.basename(member).lower() == "godmode9.firm":
                                zf.extract(member, TEMP_DIR)
                                shutil.move(os.path.join(TEMP_DIR, member), os.path.join(LUMA_PAYLOADS_FULL_PATH, "GodMode9.firm"))
                                self.log_message(f"Extracted GodMode9.firm to {LUMA_PAYLOADS_FULL_PATH}")
                            elif "gm9/scripts/" in member:
                                zf.extract(member, DOWNLOAD_DIR)
                                self.log_message(f"Extracted {member} to {DOWNLOAD_DIR}")
                    elif name == "Luma3DS":
                        zf.extractall(DOWNLOAD_DIR)
                        self.log_message(f"Extracted Luma3DS contents to {DOWNLOAD_DIR}.")
                os.remove(temp_filepath)
            else:
                final_dest_path = LUMA_PAYLOADS_FULL_PATH if original_filename.lower().endswith(".firm") else DOWNLOAD_DIR
                shutil.move(temp_filepath, os.path.join(final_dest_path, original_filename))
                self.log_message(f"Moved '{original_filename}' to '{os.path.basename(final_dest_path)}/' folder.")

        except Exception as e:
            self.log_message(f"Error during organization of {original_filename}: {e}.")
    
    def _verify_files(self):
        """Verifies that critical files exist in their final locations."""
        files_to_check = {
            "GodMode9.firm": os.path.join(LUMA_PAYLOADS_FULL_PATH, "GodMode9.firm"),
            "Luma's boot.firm": os.path.join(DOWNLOAD_DIR, "boot.firm"),
            "x_finalize_helper.firm": os.path.join(LUMA_PAYLOADS_FULL_PATH, "x_finalize_helper.firm"),
            "finalize.romfs": os.path.join(DOWNLOAD_DIR, "finalize.romfs")
        }
        for name, path in files_to_check.items():
            if os.path.exists(path):
                self.log_message(f"Verification: {name} found. OK.")
            else:
                self.log_message(f"WARNING: {name} NOT FOUND. Manual check needed!")

    def _copy_to_destination(self):
        """Copy the contents of the staging directory to the user-selected destination."""
        destination_dir = self.output_dir_var.get()
        if not destination_dir or not os.path.isdir(destination_dir):
            return

        self.log_message(f"\n--- Copying files to {destination_dir} ---")
        self.update_status("Copying to destination...")

        # This needs to run on the main thread for the messagebox to work correctly
        self.root.after(0, self._confirm_and_copy, destination_dir)

    def _confirm_and_copy(self, destination_dir):
        """Show confirmation and perform the copy. Must be called from main thread."""
        confirm_message = (
            f"This will merge the contents of '{DOWNLOAD_DIR}' into '{destination_dir}'.\n\n"
            "• New files will be added.\n"
            "• Existing files will be updated/overwritten.\n"
            "• Other files on the destination will NOT be deleted.\n\n"
            "Do you want to proceed?")
        if self.show_custom_confirm("Confirm Merge", confirm_message, width=550, height=400):
            try:
                # shutil.copytree with dirs_exist_ok=True is perfect for this
                shutil.copytree(DOWNLOAD_DIR, destination_dir, dirs_exist_ok=True)
                self.log_message(f"Successfully copied files to {destination_dir}")
                self.update_status("Copy complete!")
            except Exception as e:
                self.log_message(f"ERROR: Failed to copy files to destination: {e}")
                self.update_status("Copy failed!")
                self.show_custom_info("Copy Error", f"Failed to copy files to '{destination_dir}':\n{e}", width=500, height=220)

    # --- Helper Methods from hatskitpro.py ---
    def show_pat_settings(self):
        """Show GitHub PAT settings dialog."""
        pat_dialog = ttk.Toplevel(self.root)
        pat_dialog.title("GitHub Personal Access Token")
        pat_dialog.geometry("500x350")
        pat_dialog.transient(self.root)
        pat_dialog.grab_set()
        
        info_frame = ttk.Frame(pat_dialog, padding=20)
        info_frame.pack(fill=BOTH, expand=True)
        
        ttk.Label(info_frame, text="GitHub Personal Access Token", font=('Segoe UI', 11, 'bold')).pack(pady=(0, 10))
        ttk.Label(info_frame, text="Enter your GitHub PAT to increase API rate limits.\nThis is optional but recommended.", wraplength=450).pack(pady=(0, 15))
        
        ttk.Label(info_frame, text="Token:").pack(anchor=W)
        pat_entry = ttk.Entry(info_frame, textvariable=self.github_pat, show="*", width=50)
        pat_entry.pack(fill=X, pady=5)
        
        save_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(info_frame, text="Save token to config file", variable=save_var, bootstyle="primary-round-toggle").pack(pady=10)
        
        button_frame = ttk.Frame(info_frame)
        button_frame.pack(pady=(15, 0))
        
        def save_pat():
            token = self.github_pat.get()
            if save_var.get():
                self.config_data['github_pat'] = token
                self.save_config()
                self.show_custom_info("Saved", "GitHub PAT saved to config.", parent=pat_dialog, width=350)
            else:
                self.config_data.pop('github_pat', None)
                self.save_config()
            pat_dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_pat, bootstyle="primary").pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=pat_dialog.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        pat_dialog.update_idletasks()
        self.center_window(pat_dialog)

    def show_custom_info(self, title, message, parent=None, width=400, height=200):
        """Show a custom centered info dialog."""
        parent_window = parent if parent else self.root
        dialog = ttk.Toplevel(parent_window)
        dialog.title(title)
        dialog.geometry(f"{width}x{height}")
        dialog.transient(parent_window)
        dialog.grab_set()

        info_frame = ttk.Frame(dialog, padding=20)
        info_frame.pack(fill=BOTH, expand=True)
        ttk.Label(info_frame, text=message, wraplength=width-50, justify=CENTER).pack(pady=20)
        ttk.Button(info_frame, text="OK", command=dialog.destroy, bootstyle="primary").pack()

        dialog.update_idletasks()
        self._do_center(dialog) # Center immediately without flicker
        self.root.wait_window(dialog)

    def show_custom_confirm(self, title, message, yes_text="Yes", no_text="No", style="primary", width=450, height=250):
        """Show a custom centered confirmation dialog that returns True or False."""
        dialog = ttk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry(f"{width}x{height}")
        dialog.transient(self.root)
        dialog.grab_set()

        result = [False] # Use a list to allow modification from inner function

        def on_yes():
            result[0] = True
            dialog.destroy()

        def on_no():
            result[0] = False
            dialog.destroy()

        info_frame = ttk.Frame(dialog, padding=20)
        info_frame.pack(fill=BOTH, expand=True)
        ttk.Label(info_frame, text=message, wraplength=width-60, justify=CENTER).pack(pady=20)

        button_frame = ttk.Frame(info_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text=yes_text, command=on_yes, bootstyle=style).pack(side=LEFT, padx=10)
        ttk.Button(button_frame, text=no_text, command=on_no, bootstyle="secondary").pack(side=LEFT, padx=10)

        dialog.update_idletasks()
        self._do_center(dialog)
        self.root.wait_window(dialog)
        return result[0]

    def center_window(self, window):
        """Center a popup window on the main window, after a short delay."""
        window.after(10, lambda: self._do_center(window))

    def _do_center(self, window):
        """Perform the actual centering logic."""
        window.update_idletasks()
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()

        window_w = window.winfo_width()
        window_h = window.winfo_height()

        x = parent_x + (parent_w // 2) - (window_w // 2)
        y = parent_y + (parent_h // 2) - (window_h // 2)

        window.geometry(f"+{x}+{y}")


def main():
    # Ensure required packages are installed (simple check)
    try:
        import requests
        import ttkbootstrap
    except ImportError:
        print("Required packages 'requests' or 'ttkbootstrap' not found.")
        print("Please install them using: pip install requests ttkbootstrap")
        sys.exit(1)

    root = ttk.Window(themename="darkly")
    app = ThreeDSUpdaterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()