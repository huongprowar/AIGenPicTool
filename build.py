#!/usr/bin/env python3
"""
Build Script for AI Image Generator
====================================

Usage:
    python build.py           # Build folder distribution
    python build.py --onefile # Build single executable
    python build.py --clean   # Clean build artifacts only
"""

import subprocess
import sys
import shutil
from pathlib import Path
import argparse


def run_command(cmd: list, description: str = "") -> bool:
    """Run a command and return success status"""
    if description:
        print(f"\n{description}...")
    print(f"  > {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def clean_build():
    """Clean previous build artifacts"""
    print("\nCleaning previous builds...")

    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.pyc', '*.pyo', '*.spec.bak']

    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"  Removing {dir_path}/")
            shutil.rmtree(dir_path)

    # Clean __pycache__ in subdirectories
    for pycache in Path('.').rglob('__pycache__'):
        if 'venv' not in str(pycache):
            print(f"  Removing {pycache}/")
            shutil.rmtree(pycache)


def install_dependencies():
    """Install required dependencies"""
    print("\nInstalling dependencies...")
    return run_command(
        [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'],
        ""
    )


def build_folder():
    """Build folder distribution using spec file"""
    print("\nBuilding folder distribution...")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        'AIImageGenerator.spec',
        '--clean',
        '--noconfirm',
    ]

    return run_command(cmd, "Running PyInstaller")


def build_onefile():
    """Build single executable"""
    print("\nBuilding single executable...")

    hidden_imports = [
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'openai',
        'google.generativeai',
        'httpx',
        'pydantic',
        'ui',
        'ui.main_window',
        'ui.create_tab',
        'ui.settings_tab',
        'ui.image_item',
        'services',
        'services.config_service',
        'services.chatgpt_service',
        'services.gemini_service',
        'utils',
        'utils.prompt_parser',
        'utils.image_downloader',
        'UnlimitedAPI',
        'UnlimitedAPI.providers',
        'UnlimitedAPI.providers.google_flow',
    ]

    excludes = [
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pytest',
    ]

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'AIImageGenerator',
    ]

    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])

    for exc in excludes:
        cmd.extend(['--exclude-module', exc])

    cmd.extend([
        '--clean',
        '--noconfirm',
        'main.py'
    ])

    return run_command(cmd, "Running PyInstaller")


def main():
    parser = argparse.ArgumentParser(description='Build AI Image Generator')
    parser.add_argument('--onefile', action='store_true', help='Build single executable')
    parser.add_argument('--clean', action='store_true', help='Clean build artifacts only')
    parser.add_argument('--no-clean', action='store_true', help='Skip cleaning before build')
    args = parser.parse_args()

    print("=" * 50)
    print("  AI Image Generator - Build Script")
    print("=" * 50)

    # Clean only mode
    if args.clean:
        clean_build()
        print("\nClean completed!")
        return

    # Install dependencies
    if not install_dependencies():
        print("\nFailed to install dependencies!")
        sys.exit(1)

    # Clean previous builds
    if not args.no_clean:
        clean_build()

    # Build
    if args.onefile:
        success = build_onefile()
        output_path = Path('dist/AIImageGenerator.exe')
    else:
        success = build_folder()
        output_path = Path('dist/AIImageGenerator/AIImageGenerator.exe')

    # Check result
    print("\n" + "=" * 50)
    if success and output_path.exists():
        print("  BUILD SUCCESSFUL!")
        print("=" * 50)
        print(f"\nOutput: {output_path}")
        if output_path.is_file():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"Size: {size_mb:.1f} MB")
        print("\nTo distribute:")
        if args.onefile:
            print("  - Copy AIImageGenerator.exe to target machine")
        else:
            print("  - Copy entire 'dist/AIImageGenerator' folder")
            print("  - Run AIImageGenerator.exe")
    else:
        print("  BUILD FAILED!")
        print("=" * 50)
        print("\nCheck error messages above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
