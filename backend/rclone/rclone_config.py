"""
Rclone configuration file parsing and manipulation
"""
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from configparser import ConfigParser, DEFAULTSECT


class RcloneConfig:
    """
    Handle reading and writing rclone configuration files
    """

    def __init__(self, config_file: str):
        """
        Initialize with path to rclone config file

        Args:
            config_file: Path to rclone.conf file
        """
        self.config_file = config_file
        self.parser = ConfigParser()

        # Create config file if it doesn't exist
        if not os.path.exists(config_file):
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w') as f:
                f.write('')

        # Read existing config
        self.reload()

    def reload(self):
        """Reload configuration from file"""
        self.parser = ConfigParser()
        if os.path.exists(self.config_file):
            self.parser.read(self.config_file)

    def list_remotes(self) -> List[str]:
        """
        List all configured remotes

        Returns:
            List of remote names
        """
        # ConfigParser returns sections which are the remote names
        return self.parser.sections()

    def get_remote(self, name: str) -> Optional[Dict[str, str]]:
        """
        Get configuration for a specific remote

        Args:
            name: Remote name

        Returns:
            Dictionary of remote configuration or None if not found
        """
        if not self.parser.has_section(name):
            return None

        return dict(self.parser.items(name))

    def get_remote_raw(self, name: str) -> Optional[str]:
        """
        Get raw configuration text for a specific remote, including comments

        Args:
            name: Remote name

        Returns:
            Raw config text including comments and the [name] line, or None if not found
        """
        if not os.path.exists(self.config_file):
            return None

        with open(self.config_file, 'r') as f:
            lines = f.readlines()

        # Find the section
        section_pattern = re.compile(r'^\[([^\]]+)\]')
        in_section = False
        section_start = -1
        section_lines = []
        comment_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for section header
            match = section_pattern.match(stripped)
            if match:
                if in_section:
                    # End of our section
                    break
                elif match.group(1) == name:
                    # Start of our section
                    in_section = True
                    section_start = i
                    # Include preceding comment lines
                    section_lines = comment_lines + [line]
                    comment_lines = []
                    continue
                else:
                    # Different section, reset comment buffer
                    comment_lines = []
                    continue

            if in_section:
                # We're in the target section
                if stripped == '' or stripped.startswith('#'):
                    # Empty line or comment within section
                    section_lines.append(line)
                elif '=' in line:
                    # Config line
                    section_lines.append(line)
                else:
                    # Probably end of section (or malformed line)
                    break
            elif stripped.startswith('#'):
                # Comment before any section - might belong to next section
                comment_lines.append(line)
            else:
                # Not in section and not a comment - reset comment buffer
                if stripped != '':
                    comment_lines = []

        if not section_lines:
            return None

        # Join and remove trailing newline
        return ''.join(section_lines).rstrip('\n')

    def update_remote_raw(self, old_name: str, new_config_text: str) -> Tuple[bool, Optional[str]]:
        """
        Update a remote's configuration in-place, preserving position and structure

        Args:
            old_name: Current remote name
            new_config_text: New configuration text (including [name] line and comments)

        Returns:
            Tuple of (success: bool, new_name: Optional[str])
            new_name will be the new remote name if it was renamed, or None if there was an error
        """
        if not os.path.exists(self.config_file):
            return False, None

        # Parse the new config to extract the new name
        new_name = None
        section_pattern = re.compile(r'^\[([^\]]+)\]')
        for line in new_config_text.split('\n'):
            match = section_pattern.match(line.strip())
            if match:
                new_name = match.group(1)
                break

        if not new_name:
            logging.error("Could not find [name] in new config text")
            return False, None

        # Read the entire file
        with open(self.config_file, 'r') as f:
            lines = f.readlines()

        # Find and replace the section
        in_section = False
        section_start = -1
        section_end = -1
        comment_start = -1

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for section header
            match = section_pattern.match(stripped)
            if match:
                if in_section:
                    # End of our section (start of next section)
                    section_end = i
                    break
                elif match.group(1) == old_name:
                    # Start of our section
                    in_section = True
                    section_start = i
                    # Check for preceding comments
                    if comment_start == -1:
                        comment_start = i
                    continue

            if in_section:
                # We're in the target section, looking for the end
                if stripped == '' or stripped.startswith('#') or '=' in line:
                    # Still in section
                    continue
                else:
                    # End of section
                    section_end = i
                    break
            elif not in_section and section_start == -1 and stripped.startswith('#'):
                # Potential comment before our section
                if comment_start == -1:
                    comment_start = i
            elif not in_section and stripped != '' and not stripped.startswith('#'):
                # Non-comment, non-empty line - reset comment tracking
                comment_start = -1

        if section_start == -1:
            # Section not found
            return False, None

        # If section_end not set, it goes to end of file
        if section_end == -1:
            section_end = len(lines)

        # Replace the section (from comment_start or section_start to section_end)
        new_lines = new_config_text.split('\n')
        # Ensure each line ends with \n
        new_lines = [line + '\n' if not line.endswith('\n') else line for line in new_lines]
        # Add blank line after section if there isn't one already
        if new_lines and not new_lines[-1].strip() == '':
            new_lines.append('\n')

        # Reconstruct the file
        result_lines = lines[:comment_start] + new_lines + lines[section_end:]

        # Write back
        with open(self.config_file, 'w') as f:
            f.writelines(result_lines)

        # Reload parser
        self.reload()

        logging.info(f"Updated remote {old_name} -> {new_name} in-place")
        return True, new_name

    def add_remote(self, name: str, config: Dict[str, str]):
        """
        Add or update a remote configuration

        Args:
            name: Remote name
            config: Dictionary of configuration options
        """
        # Remove remote if it exists
        if self.parser.has_section(name):
            self.parser.remove_section(name)

        # Add new remote
        self.parser.add_section(name)
        for key, value in config.items():
            self.parser.set(name, key, str(value))

        # Save to file
        self.save()

    def delete_remote(self, name: str) -> bool:
        """
        Delete a remote configuration

        Args:
            name: Remote name

        Returns:
            True if remote was deleted, False if it didn't exist
        """
        if not self.parser.has_section(name):
            return False

        self.parser.remove_section(name)
        self.save()
        return True

    def save(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            self.parser.write(f)
        logging.info(f"Saved rclone config to {self.config_file}")



class RemoteTemplate:
    """
    Handle parsing and rendering of remote templates
    """

    def __init__(self, template_file: str):
        """
        Initialize with path to template file

        Args:
            template_file: Path to template file
        """
        self.template_file = template_file
        self.templates: Dict[str, Dict[str, any]] = {}

        if template_file and os.path.exists(template_file):
            self.load()
        else:
            logging.warning(f"Template file not found: {template_file}")

    def load(self):
        """Load templates from file"""
        self.templates = {}

        with open(self.template_file, 'r') as f:
            content = f.read()

        # Parse template file (similar to rclone.conf format)
        current_template = None
        current_config = {}
        current_fields = []

        for line in content.split('\n'):
            line = line.rstrip()

            # Skip empty lines
            if not line:
                continue

            # Skip comments (but save them for description)
            if line.startswith('#'):
                # Comment before section might be description
                continue

            # Section header [template_name]
            if line.startswith('[') and line.endswith(']'):
                # Save previous template
                if current_template:
                    self.templates[current_template] = {
                        'config': current_config,
                        'fields': current_fields,
                    }

                # Start new template
                current_template = line[1:-1]
                current_config = {}
                current_fields = []
                continue

            # Configuration line: key = value
            if '=' in line and current_template:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Check if value is a template variable {{ field_name }}
                template_match = re.match(r'{{\s*(.+?)\s*}}', value)
                if template_match:
                    field_name = template_match.group(1)
                    current_fields.append({
                        'key': key,
                        'label': field_name,
                    })
                    current_config[key] = f'{{{{{field_name}}}}}'
                else:
                    # Static value
                    current_config[key] = value

        # Save last template
        if current_template:
            self.templates[current_template] = {
                'config': current_config,
                'fields': current_fields,
            }

        logging.info(f"Loaded {len(self.templates)} templates from {self.template_file}")

    def list_templates(self) -> List[str]:
        """
        List all available templates

        Returns:
            List of template names
        """
        return list(self.templates.keys())

    def get_template(self, name: str) -> Optional[Dict]:
        """
        Get a template by name

        Args:
            name: Template name

        Returns:
            Template dictionary with 'config' and 'fields' keys, or None if not found
        """
        return self.templates.get(name)

    def render_template(self, template_name: str, values: Dict[str, str]) -> Dict[str, str]:
        """
        Render a template with provided values

        Args:
            template_name: Name of template to render
            values: Dictionary of field values (field_label -> value)

        Returns:
            Rendered configuration dictionary

        Raises:
            ValueError: If template not found or missing required fields
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")

        config = template['config'].copy()
        fields = template['fields']

        # Check all required fields are provided
        required_labels = {f['label'] for f in fields}
        provided_labels = set(values.keys())
        missing = required_labels - provided_labels
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Render template by replacing {{ field }} placeholders
        rendered = {}
        for key, value in config.items():
            # Check if value is a template
            if value.startswith('{{') and value.endswith('}}'):
                field_label = value[2:-2].strip()
                rendered[key] = values.get(field_label, value)
            else:
                rendered[key] = value

        return rendered
