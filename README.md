# 3DS Starter Pack Downloader
![https://github.com/sthetix/3DS-Starterpack/releases/download/1.0.1/title.jpg](https://github.com/sthetix/3DS-Starterpack/releases/download/1.0.1/title.jpg)

A streamlined tool for downloading essential files needed to finalize your Nintendo 3DS custom firmware setup.

----------

## What is this?

This Python script automatically downloads the latest versions of core files required for the "Finalizing Setup" step when installing custom firmware on your 3DS console. It eliminates the need to manually hunt down individual releases from multiple GitHub repositories.

----------

## What gets downloaded?

-   **Luma3DS** - Latest custom firmware (`boot.firm`)
    
-   **GodMode9** - File system access tool with scripts
    
-   **Finalize Helper** - Required files for setup completion
    

All files are automatically organized in the proper SD card structure, ready to copy directly to your 3DS.

----------

## Requirements

-   Python 3.6 or newer
    
-   Internet connection
    
-   Windows, macOS, or Linux
    

----------

## Usage

### Option 1: Python Script

Bash

```
python 3ds_starter_pack_updater.py

```

### Option 2: Executable (Windows)

Download and run `3DS.Starter.Pack.Updater.exe` from the [releases page](https://github.com/sthetix/3DS-Starterpack/releases) (replace with your actual releases page link).

----------

### Optional Parameters:

-   `--clear-cache` - Force fresh downloads, ignoring cached data
    

----------

## Features

-   **Smart caching** - Avoids GitHub API rate limits with 24-hour cache
    
-   **Rate limit handling** - Optional GitHub token support for higher limits
    
-   **Clean organization** - Files placed in correct SD card structure
    
-   **Error resilience** - Automatic retries and clear error messages
    

----------

## Output

The script creates a `3DS Starter Pack` folder containing all files organized for your SD card. Simply copy the contents to your SD card root and follow the 3DS Hacking Guide to complete your setup.

----------

## GitHub Token (Optional)

For higher API rate limits, set a GitHub personal access token:

### Windows:

DOS

```
setx GITHUB_TOKEN "your_token_here"

```

### macOS/Linux:

Bash

```
export GITHUB_TOKEN="your_token_here"

```

Create tokens at: [https://github.com/settings/tokens](https://github.com/settings/tokens) (requires 'public_repo' scope)

----------

## License

This project is licensed under the [MIT License](https://www.google.com/search?q=LICENSE) (assuming you have a `LICENSE` file in your repository).
