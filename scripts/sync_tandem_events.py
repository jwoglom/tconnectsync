#!/usr/bin/env python3
"""
Sync event definitions from Tandem's official webapp and regenerate event classes.

Extracts the complete events.json from the JSON.parse() statement embedded in
Tandem's reports module JavaScript, updates local events.json, and regenerates
events.py with all event class definitions.

Usage:
    python3 scripts/sync_tandem_events.py [--output FILE] <URL>

Example:
    python3 scripts/sync_tandem_events.py \\
      https://modules.us.tandemdiabetes.com/webapp/modules/reports-module/v1.8.0/2451.97042bc1.chunk.js
"""

import sys
import json
import subprocess
import requests
from pathlib import Path


DEFAULT_EVENTS_FILE = "tconnectsync/eventparser/events.json"
DEFAULT_GENERATOR = "build_events.py"


def fetch_module(url):
    """Fetch the minified JavaScript module from Tandem."""
    print(f"Fetching Tandem module...", file=sys.stderr)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    content = response.text
    print(f"Fetched {len(content):,} bytes", file=sys.stderr)
    return content


def extract_events_json_from_parse(js_content):
    """
    Extract the complete events.json from the JSON.parse() statement.

    Finds: JSON.parse('{"events":{...}}')
    And returns the parsed events dictionary.
    """
    start = js_content.find("JSON.parse('")
    if start < 0:
        return None

    start += len("JSON.parse('")

    # Find the matching closing brace
    brace_count = 0
    end = start
    escape_next = False

    for i in range(start, len(js_content)):
        char = js_content[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    if brace_count != 0:
        return None

    json_str = js_content[start:end]

    # Unescape the string
    json_str = json_str.replace('\\"', '"')

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def load_existing_events(filepath):
    """Load the existing events.json file."""
    if not Path(filepath).exists():
        return {"events": {}}

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            print(f"Loaded {len(data.get('events', {}))} existing events", file=sys.stderr)
            return data
    except Exception as e:
        print(f"Warning: Could not load existing events.json: {e}", file=sys.stderr)
        return {"events": {}}


def merge_events(existing_data, extracted_data):
    """
    Merge extracted events with existing events.

    Keeps all existing events and updates/adds with extracted ones.
    """
    existing = existing_data.get('events', {})
    extracted = extracted_data.get('events', {})

    before_count = len(existing)

    # Add/update extracted events
    existing.update(extracted)

    after_count = len(existing)
    added = after_count - before_count

    if added > 0:
        print(f"Added {added} new events from Tandem module", file=sys.stderr)
    else:
        print(f"Updated {len(extracted)} events from Tandem module", file=sys.stderr)

    return existing_data


def write_events_file(filepath, data):
    """Write events.json with proper formatting."""
    if 'events' in data:
        data['events'] = {
            k: data['events'][k]
            for k in sorted(data['events'].keys(), key=lambda x: int(x))
        }

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {len(data.get('events', {}))} events to {filepath}", file=sys.stderr)


def regenerate_events_py(events_json_path, generator_name):
    """Regenerate events.py from updated events.json."""
    events_dir = Path(events_json_path).parent
    generator_path = events_dir / generator_name

    if not generator_path.exists():
        print(f"⚠ Generator not found at {generator_path}", file=sys.stderr)
        return False

    print(f"Regenerating events.py...", file=sys.stderr)

    try:
        result = subprocess.run(
            [sys.executable, generator_name],
            cwd=str(events_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Write generated code to events.py
            events_py = events_dir / 'events.py'
            events_py.write_text(result.stdout)
            print(f"✓ events.py regenerated ({len(result.stdout):,} bytes)", file=sys.stderr)
            return True
        else:
            print(f"✗ Generator failed: {result.stderr}", file=sys.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("✗ Generator timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error running generator: {e}", file=sys.stderr)
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Sync event definitions from Tandem and regenerate events.py'
    )
    parser.add_argument('url', help='URL to Tandem JavaScript module')
    parser.add_argument('--output', default=DEFAULT_EVENTS_FILE, help='Output events.json path')
    parser.add_argument('--no-generate', action='store_true', help='Skip events.py regeneration')

    args = parser.parse_args()

    try:
        js_content = fetch_module(args.url)

        extracted_data = extract_events_json_from_parse(js_content)
        if not extracted_data:
            print("✗ Could not extract events.json from Tandem module", file=sys.stderr)
            sys.exit(1)

        extracted_events = extracted_data.get('events', {})
        print(f"✓ Extracted {len(extracted_events)} events from Tandem module", file=sys.stderr)

        existing_data = load_existing_events(args.output)
        merged_data = merge_events(existing_data, extracted_data)
        write_events_file(args.output, merged_data)

        if not args.no_generate:
            regenerate_events_py(args.output, DEFAULT_GENERATOR)

        print(f"\n✓ Done", file=sys.stderr)

    except requests.exceptions.RequestException as e:
        print(f"✗ Network error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
