#!/usr/bin/env python3
"""
Sync event definitions from Tandem's official webapp and regenerate event classes.

Tandem's reports module embeds its event schema as a YAML string
(src/event-decoder/EventSchema/eventSchema.yml) and converts it at runtime with
schemaFromYmlEvents() in src/event-decoder/Decoder/ymlSchemaAdapter.ts. This
script extracts that YAML from the module's JavaScript, applies a line-for-line
port of the same conversion, writes the result to events.json, and regenerates
events.py.

Offsets in events.json are the schema's own (YAML) offsets. Like Tandem's
decoder (ymlOffsetToDataFieldOffset), build_events.py converts them to byte
offsets when generating the binary parsers.

Usage:
    python3 scripts/sync_tandem_events.py [--output FILE] <URL or local .js path>

Example:
    python3 scripts/sync_tandem_events.py \\
      https://modules.us.tandemdiabetes.com/webapp/modules/reports-module/v2.0.0/static/js/async/5156.b2274d34.js
"""

import re
import sys
import json
import subprocess
from pathlib import Path

import requests
import yaml


DEFAULT_EVENTS_FILE = "tconnectsync/eventparser/events.json"
DEFAULT_GENERATOR = "build_events.py"

YAML_START = "- name: LID_"


def fetch_module(source):
    """Fetch the minified JavaScript module from Tandem, or read a saved copy."""
    if Path(source).exists():
        content = Path(source).read_text()
        print(f"Read {len(content):,} bytes from {source}", file=sys.stderr)
        return content

    print(f"Fetching Tandem module...", file=sys.stderr)
    response = requests.get(source, timeout=30)
    response.raise_for_status()
    content = response.text
    print(f"Fetched {len(content):,} bytes", file=sys.stderr)
    return content


def unescape_js_string(s):
    """Unescape the body of a JavaScript string literal."""
    def repl(m):
        esc = m.group(1)
        if esc[0] in 'ux' and len(esc) > 1:
            return chr(int(esc[1:], 16))
        return {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}.get(esc, esc)
    return re.sub(r'\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)', repl, s, flags=re.DOTALL)


def extract_schema_yaml(js_content):
    """
    Extract the event schema YAML from the string literal embedded in the
    module, e.g. (0,t(18459).T5)('- name: LID_BASAL_RATE_CHANGE\\n  id: 3...').
    """
    start = -1
    for quote in ("'", '"', '`'):
        start = js_content.find(quote + YAML_START)
        if start >= 0:
            break
    if start < 0:
        return None

    i = start + 1
    while i < len(js_content):
        char = js_content[i]
        if char == '\\':
            i += 2
            continue
        if char == quote:
            return unescape_js_string(js_content[start + 1:i])
        i += 1
    return None


# Port of src/event-decoder/Decoder/ymlSchemaAdapter.ts

FIELD_TYPES = ['float32', 'int32', 'uint32', 'int16', 'uint16', 'int8', 'uint8']

DICTIONARY_BY_FIELD_KEY = {
    'alertId': 'alerts',
    'alarmId': 'alarms',
    'malfId': 'malfs',
    'reminderId': 'reminders',
    'infoId': 'infos',
    'dalertId': 'dalerts',
    'faultId': 'faults',
}


def parse_integer(value):
    if isinstance(value, bool):
        raise ValueError(f"Unable to parse integer from value '{value}'")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        m = re.match(r'\s*([+-]?\d+)', value)
        if m:
            return int(m.group(1))
    raise ValueError(f"Unable to parse integer from value '{value}'")


def normalize_type(raw_type, event_name, field_name):
    normalized = raw_type.lower()
    if normalized in FIELD_TYPES:
        return normalized
    raise ValueError(f"Unsupported field type '{raw_type}' for {event_name}.{field_name}")


def to_pipeline_property_name(name):
    # This function was made specifically to align names of data properties with the data processing service.
    trimmed = re.sub(r'[_-]+', ' ', (name or '').strip())
    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+', trimmed)
    pascal = ''.join(w[0].upper() + w[1:].lower() for w in words)
    return pascal[0].lower() + pascal[1:] if pascal else ''


def normalize_uom(uom):
    if not uom:
        return None
    trimmed = str(uom).strip()
    if not trimmed or trimmed == '--' or trimmed.lower() == 'n/a':
        return None
    return trimmed


def parse_ratio_from_uom(raw_uom):
    if not raw_uom:
        return None
    m = re.search(r'1ct\s*=\s*([0-9]*\.?[0-9]+)', str(raw_uom), re.IGNORECASE)
    return float(m.group(1)) if m else None


def is_bitmask_field(raw_uom):
    return raw_uom is not None and str(raw_uom).strip().lower() == 'bitmask'


def build_enum_map(enum_mapping):
    if not isinstance(enum_mapping, list) or not enum_mapping:
        return None
    m = {}
    for item in enum_mapping:
        if not item or item.get('enum') is None or item.get('enumFriendlyName') is None:
            continue
        m[str(item['enum'])] = str(item['enumFriendlyName'])
    return m or None


def build_transforms(field_name, raw_uom, enum_mapping):
    transforms = []

    dictionary = DICTIONARY_BY_FIELD_KEY.get(field_name)
    if dictionary:
        transforms.append(['dictionary', dictionary])

    enum_map = build_enum_map(enum_mapping)
    if enum_map:
        transforms.append(['bitmask' if is_bitmask_field(raw_uom) else 'enum', enum_map])

    ratio = parse_ratio_from_uom(raw_uom)
    if ratio is not None:
        transforms.append(['ratio', ratio])
    elif field_name == 'rate' and isinstance(raw_uom, str) and re.search(r'/10\b', raw_uom):
        transforms.append(['ratio', 0.1])

    if isinstance(raw_uom, str) and raw_uom.lower() == 'ascii':
        transforms.append(['bytes2str'])

    return transforms or None


def build_field(event_name, field):
    if not field.get('name') or not field.get('type') or field.get('offset') is None:
        return None

    key = to_pipeline_property_name(field['name'])
    definition = {
        'type': normalize_type(field['type'], event_name, field['name']),
        'offset': parse_integer(field['offset']),
    }
    uom = normalize_uom(field.get('uom'))
    if uom is not None:
        definition['uom'] = uom
    transform = build_transforms(key, field.get('uom'), field.get('enumMapping'))
    if transform is not None:
        definition['transform'] = transform
    return key, definition


def schema_from_yml_events(events):
    schema_events = {}
    for yml_event in events:
        if not yml_event or not yml_event.get('name') or yml_event.get('id') is None:
            continue

        event_id = parse_integer(yml_event['id'])
        fields = {}
        for field in yml_event.get('fields') or []:
            built = build_field(yml_event['name'], field)
            if not built:
                continue
            key, definition = built
            if key.startswith('spare'):
                continue
            fields[key] = definition

        schema_events[str(event_id)] = {
            'name': yml_event['name'],
            'data': fields,
        }
    return {'events': schema_events}


def schema_from_yml_string(yml):
    parsed = yaml.safe_load(yml)
    if not isinstance(parsed, list):
        raise ValueError('Expected top-level YML document to be an array of events.')
    return schema_from_yml_events(parsed)


def write_events_file(filepath, data):
    """Write events.json with proper formatting."""
    data['events'] = {
        k: data['events'][k]
        for k in sorted(data['events'].keys(), key=lambda x: int(x))
    }

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    print(f"Wrote {len(data['events'])} events to {filepath}", file=sys.stderr)


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
    parser.add_argument('source', help='URL to (or saved copy of) the Tandem reports-module JavaScript chunk')
    parser.add_argument('--output', default=DEFAULT_EVENTS_FILE, help='Output events.json path')
    parser.add_argument('--yaml-output', help='Also save the extracted schema YAML to this path')
    parser.add_argument('--no-generate', action='store_true', help='Skip events.py regeneration')

    args = parser.parse_args()

    try:
        js_content = fetch_module(args.source)

        yml = extract_schema_yaml(js_content)
        if not yml:
            print("✗ Could not find the event schema YAML in the Tandem module", file=sys.stderr)
            sys.exit(1)

        if args.yaml_output:
            Path(args.yaml_output).write_text(yml)

        schema = schema_from_yml_string(yml)
        print(f"✓ Extracted {len(schema['events'])} events from Tandem module", file=sys.stderr)

        # events.json mirrors Tandem's schema exactly; anything Tandem's schema
        # lacks belongs in custom_events.json.
        write_events_file(args.output, schema)

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
