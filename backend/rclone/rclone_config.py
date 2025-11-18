"""
Rclone configuration file parsing and manipulation
"""
import os
import re
import logging
from typing import Dict, List, Optional
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
