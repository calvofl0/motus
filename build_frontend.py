"""
Hatchling build hook to build Vue frontend before packaging
"""
import os
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Build Vue frontend before packaging"""

    def initialize(self, version, build_data):
        """Run npm build to generate static frontend files"""
        frontend = Path(self.root) / 'frontend'
        frontend_dist = Path(self.root) / 'src' / 'motus' / 'static'

        # Check if Node.js and npm are available
        try:
            subprocess.run(
                ['npm', '--version'],
                check=True,
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                "\n" + "=" * 70,
                file=sys.stderr
            )
            print(
                "  ERROR: npm is not installed or not in PATH",
                file=sys.stderr
            )
            print(
                "  Motus requires Node.js and npm to build the frontend.",
                file=sys.stderr
            )
            print(
                "\n  Please install Node.js from: https://nodejs.org/",
                file=sys.stderr
            )
            print(
                "  Or use your system package manager:",
                file=sys.stderr
            )
            print(
                "    - Ubuntu/Debian: sudo apt install nodejs npm",
                file=sys.stderr
            )
            print(
                "    - macOS: brew install node",
                file=sys.stderr
            )
            print(
                "    - Windows: Download from https://nodejs.org/",
                file=sys.stderr
            )
            print(
                "=" * 70 + "\n",
                file=sys.stderr
            )
            sys.exit(1)

        # Check if static directory already exists and is up to date
        if frontend_dist.exists():
            # If static directory exists, we assume it's already built
            # This allows pre-building for distribution
            print("src/motus/static/ already exists, skipping build")
            return

        # Install npm dependencies if needed
        node_modules = frontend / 'node_modules'
        if not node_modules.exists():
            print("Installing npm dependencies...")
            subprocess.run(
                ['npm', 'install'],
                cwd=frontend,
                check=True
            )

        # Build Vue frontend
        print("Building Vue frontend...")
        subprocess.run(
            ['npm', 'run', 'build'],
            cwd=frontend,
            check=True
        )

        # Verify build output
        if not frontend_dist.exists():
            print(
                "ERROR: Vue build failed - src/motus/static/ not created",
                file=sys.stderr
            )
            sys.exit(1)

        print("Vue frontend built successfully")
