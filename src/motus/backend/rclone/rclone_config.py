"""
Rclone configuration file parsing and manipulation
"""
import os
import re
import ast
import logging
from typing import Dict, List, Optional, Tuple
from configparser import ConfigParser, DEFAULTSECT


def markdown_links_to_html(text: str) -> str:
    """
    Convert markdown links [text](url) to HTML <a> tags

    Args:
        text: Text with markdown links

    Returns:
        Text with HTML links
    """
    # Pattern: [link text](url)
    pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    return re.sub(pattern, r'<a href="\2" target="_blank">\1</a>', text)


class RcloneConfig:
    """
    Handle reading and writing rclone configuration files

    Supports a two-tier configuration system:
    - User config: Primary writable config (user's master config)
    - Readonly config: Secondary read-only config (from --extra-remotes)
    - Merged config: Runtime-only merged config (used by rclone operations)
    """

    def __init__(self, config_file: str, readonly_config_file: str = None, cache_dir: str = None):
        """
        Initialize with path to rclone config file

        Args:
            config_file: Path to user's rclone.conf file (master config)
            readonly_config_file: Optional path to readonly remotes config file
            cache_dir: Optional cache directory for merged config file
        """
        self.user_config_file = config_file  # Master writable config
        self.readonly_config_file = readonly_config_file  # Readonly config source
        self.readonly_remotes: set = set()  # Names of readonly remotes

        # Determine which config file to use for operations
        if readonly_config_file and cache_dir:
            # Use merged config for rclone operations
            self.merged_config_file = os.path.join(cache_dir, 'rclone_merged.conf')
            self.config_file = self.merged_config_file  # Use merged for operations
        else:
            # No readonly config, use user config directly
            self.merged_config_file = None
            self.config_file = config_file

        self.parser = ConfigParser()

        # Create user config file if it doesn't exist
        if not os.path.exists(config_file):
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w') as f:
                f.write('')

        # Create merged config if needed
        if self.merged_config_file:
            self._create_merged_config()
        else:
            # Read user config directly
            self.reload()

    def reload(self):
        """Reload configuration from file"""
        self.parser = ConfigParser()
        if os.path.exists(self.config_file):
            self.parser.read(self.config_file)

    def _create_merged_config(self):
        """
        Create merged configuration file from user config + readonly config

        User's remotes take precedence. Readonly remotes with duplicate names are ignored.
        This method is called on initialization and after user config modifications.
        """
        import shutil
        from configparser import ConfigParser

        # Start with a copy of user's config
        shutil.copy2(self.user_config_file, self.merged_config_file)
        logging.info(f"Created merged config at {self.merged_config_file}")

        # If no readonly config, we're done
        if not self.readonly_config_file or not os.path.exists(self.readonly_config_file):
            self.reload()
            return

        # Load user config to check for duplicates
        user_parser = ConfigParser()
        user_parser.read(self.user_config_file)
        user_remotes = set(user_parser.sections())

        # Load readonly config
        readonly_parser = ConfigParser()
        readonly_parser.read(self.readonly_config_file)

        # Track which remotes are readonly (and not duplicates)
        self.readonly_remotes = set()

        # Append readonly remotes that don't conflict with user's remotes
        with open(self.merged_config_file, 'a') as f:
            for section in readonly_parser.sections():
                if section in user_remotes:
                    # Conflict: user's remote wins, don't add readonly version
                    logging.warning(
                        f"Readonly remote '{section}' conflicts with user's remote - "
                        f"using user's version (user's remote is writable)"
                    )
                else:
                    # No conflict: add readonly remote
                    f.write(f'\n[{section}]\n')
                    for key, value in readonly_parser.items(section):
                        f.write(f'{key} = {value}\n')
                    self.readonly_remotes.add(section)
                    logging.info(f"Added readonly remote '{section}' to merged config")

        # Reload merged config into parser
        self.reload()
        logging.info(
            f"Merged config created: {len(user_remotes)} user remotes, "
            f"{len(self.readonly_remotes)} readonly remotes"
        )

    def is_readonly_remote(self, name: str) -> bool:
        """
        Check if a remote is from the readonly configuration

        Args:
            name: Remote name

        Returns:
            True if remote is readonly, False otherwise
        """
        return name in self.readonly_remotes

    def _regenerate_merged_config(self):
        """
        Regenerate merged config after user config has been modified

        This ensures the merged config stays in sync with user's changes.
        """
        if self.merged_config_file:
            logging.info("Regenerating merged config after user config modification")
            self._create_merged_config()

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

        Raises:
            ValueError: If trying to update a readonly remote
        """
        # Check if this is a readonly remote
        if self.is_readonly_remote(old_name):
            raise ValueError(f"Cannot update readonly remote: {old_name}")

        # Determine which config file to work with
        target_file = self.user_config_file if self.merged_config_file else self.config_file

        if not os.path.exists(target_file):
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
        with open(target_file, 'r') as f:
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

        # Write back to user config
        with open(target_file, 'w') as f:
            f.writelines(result_lines)

        # Regenerate merged config if needed
        self._regenerate_merged_config()

        # Reload parser
        self.reload()

        logging.info(f"Updated remote {old_name} -> {new_name} in-place")
        return True, new_name

    def add_remote_raw(self, raw_config_text: str) -> Tuple[bool, Optional[str]]:
        """
        Add a new remote from raw configuration text

        Args:
            raw_config_text: Raw config text including [name] section and all fields

        Returns:
            Tuple of (success: bool, remote_name: Optional[str])
        """
        # Parse to extract remote name
        section_pattern = re.compile(r'^\[([^\]]+)\]')
        remote_name = None
        for line in raw_config_text.split('\n'):
            match = section_pattern.match(line.strip())
            if match:
                remote_name = match.group(1)
                break

        if not remote_name:
            logging.error("No [remote_name] section found in raw config")
            return False, None

        # Determine which config file to work with
        target_file = self.user_config_file if self.merged_config_file else self.config_file

        # Check if remote already exists
        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                content = f.read()
            if f'[{remote_name}]' in content:
                logging.error(f"Remote {remote_name} already exists")
                return False, None

        # Append the new remote to the user config file
        with open(target_file, 'a') as f:
            # Ensure there's a blank line before the new remote
            f.write('\n')
            f.write(raw_config_text)
            if not raw_config_text.endswith('\n'):
                f.write('\n')

        # Regenerate merged config if needed
        self._regenerate_merged_config()

        self.reload()
        logging.info(f"Added new remote {remote_name} from raw config")
        return True, remote_name

    def add_remote(self, name: str, config: Dict[str, str]):
        """
        Add or update a remote configuration

        Args:
            name: Remote name
            config: Dictionary of configuration options

        Raises:
            ValueError: If trying to add/update a readonly remote
        """
        # Check if this is a readonly remote
        if self.is_readonly_remote(name):
            raise ValueError(f"Cannot modify readonly remote: {name}")

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

        Raises:
            ValueError: If trying to delete a readonly remote
        """
        # Check if this is a readonly remote
        if self.is_readonly_remote(name):
            raise ValueError(f"Cannot delete readonly remote: {name}")

        if not self.parser.has_section(name):
            return False

        self.parser.remove_section(name)
        self.save()
        return True

    def save(self):
        """
        Save configuration to file

        When using merged config, this saves to the user's config file
        and then regenerates the merged config.
        """
        # Determine which file to save to
        if self.merged_config_file:
            # Save to user's config, then regenerate merged
            target_file = self.user_config_file
        else:
            # Save to the main config file
            target_file = self.config_file

        with open(target_file, 'w') as f:
            self.parser.write(f)
        logging.info(f"Saved rclone config to {target_file}")

        # Regenerate merged config if we're using one
        self._regenerate_merged_config()

    def merge_remotes_from_file(self, source_config_file: str) -> int:
        """
        Merge remotes from another rclone config file into this config

        Only adds remotes that don't already exist. Existing remotes are not overwritten.

        Args:
            source_config_file: Path to rclone config file to merge from

        Returns:
            int: Number of remotes added

        Raises:
            FileNotFoundError: If source_config_file doesn't exist
        """
        import configparser

        if not os.path.exists(source_config_file):
            raise FileNotFoundError(f"Source config file not found: {source_config_file}")

        # Parse source config file
        source_parser = configparser.ConfigParser()
        source_parser.read(source_config_file)

        # Get existing remotes
        existing_remotes = set(self.list_remotes())

        # Add new remotes
        added_count = 0
        for section in source_parser.sections():
            if section not in existing_remotes:
                # Add this remote
                self.parser.add_section(section)
                for key, value in source_parser.items(section):
                    self.parser.set(section, key, value)
                logging.info(f"Added remote '{section}' from {source_config_file}")
                added_count += 1
            else:
                logging.debug(f"Skipping remote '{section}' - already exists")

        # Save if any remotes were added
        if added_count > 0:
            self.save()
            logging.info(f"Merged {added_count} remote(s) from {source_config_file}")
        else:
            logging.info(f"No new remotes to add from {source_config_file}")

        return added_count

    def resolve_alias_chain(self, remote_name: str, path: str = '', visited: set = None) -> Tuple[str, str]:
        """
        Recursively resolve an alias remote to its underlying remote

        This method follows alias chains to find the actual remote that stores the data.
        For example, if you have:
            - MyAlias -> points to MyAlias2:/folder1
            - MyAlias2 -> points to onedrive:/folder2
        Then resolve_alias_chain('MyAlias', '/mypath') returns ('onedrive', '/folder2/folder1/mypath')

        Args:
            remote_name: Name of the remote to resolve
            path: Path within the remote
            visited: Set of visited remotes (used internally to prevent infinite loops)

        Returns:
            Tuple of (resolved_remote_name, resolved_path)

        Raises:
            ValueError: If remote not found or circular alias reference detected
        """
        if visited is None:
            visited = set()

        # Prevent infinite loops
        if remote_name in visited:
            raise ValueError(f"Circular alias reference detected: {remote_name}")
        visited.add(remote_name)

        # Get remote config
        config = self.get_remote(remote_name)
        if not config:
            raise ValueError(f"Remote not found: {remote_name}")

        # Check if this is an alias
        if config.get('type') != 'alias':
            # Not an alias, return as-is
            return remote_name, path

        # Get the target remote from alias config
        target = config.get('remote', '')
        if not target:
            raise ValueError(f"Alias remote '{remote_name}' has no target configured")

        # Parse target (format: "remote:path" or just "remote" or local path)
        if ':' in target:
            target_remote, target_path = target.split(':', 1)
        else:
            target_remote = target
            target_path = ''

        # Combine paths: target path + our path
        if target_path and path:
            combined_path = f"{target_path.rstrip('/')}/{path.lstrip('/')}"
        elif target_path:
            combined_path = target_path
        else:
            combined_path = path

        # Check if target_remote is a configured remote or a local path
        # If it's not in the list of configured remotes, it's a local path
        configured_remotes = self.list_remotes()
        if target_remote not in configured_remotes:
            # Target is a local path, not another remote - end of chain
            return target_remote, combined_path

        # Target is another remote - recursively resolve it
        return self.resolve_alias_chain(target_remote, combined_path, visited)



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

                # Check if value is a template variable {{ field_spec }}
                template_match = re.match(r'{{\s*(.+?)\s*}}', value)
                if template_match:
                    field_spec = template_match.group(1).strip()

                    # Try to parse as Python literal (dict or string)
                    try:
                        parsed = ast.literal_eval(field_spec)

                        if isinstance(parsed, dict):
                            # Dict format: {{ {"label": "...", "help": "..."} }}
                            label = parsed.get('label', key)
                            help_text = parsed.get('help', '')

                            # Convert markdown links in help text to HTML
                            if help_text:
                                help_text = markdown_links_to_html(help_text)

                            current_fields.append({
                                'key': key,
                                'label': label,
                                'help': help_text,
                            })
                        elif isinstance(parsed, str):
                            # String format: {{ "Field Label" }}
                            current_fields.append({
                                'key': key,
                                'label': parsed,
                                'help': '',
                            })
                        else:
                            # Unexpected type - treat as raw string
                            current_fields.append({
                                'key': key,
                                'label': field_spec,
                                'help': '',
                            })
                    except (ValueError, SyntaxError):
                        # Not valid Python literal - treat as raw string (old format)
                        # This maintains backward compatibility with {{ field_name }}
                        current_fields.append({
                            'key': key,
                            'label': field_spec,
                            'help': '',
                        })

                    current_config[key] = f'{{{{{field_spec}}}}}'
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
