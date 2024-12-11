header = '''# THIS FILE IS AUTOGENERATED. DO NOT EDIT.
import struct
import logging
from dataclasses import dataclass
from enum import Enum, IntFlag
from .raw_event import RawEvent, BaseEvent

logger = logging.getLogger(__name__)

EVENT_LEN = 26

'''

TYPE_TO_STRUCT = {
    'uint8': '>B',
    'int8': '>b',
    'uint16': '>H',
    'int16': '>h',
    'uint32': '>I',
    'float32': '>f',
}

for k, v in TYPE_TO_STRUCT.items():
    header += f"{k.upper()} = '{v}'\n"

TYPE_TO_PYOBJ = {
    'uint8': 'int',
    'int8': 'int',
    'uint16': 'int',
    'int16': 'int',
    'uint32': 'int',
    'float32': 'float',
}

HEADER_SIZE = 10
def unpack_command_for(field_def):
    return f'struct.unpack_from({field_def["type"].upper()}, raw[:EVENT_LEN], {HEADER_SIZE + field_def["offset"]})'

TEMPLATE = '''
@dataclass
class {name}(BaseEvent):
    """{id}: {raw_name}"""
    ID = {id}
    NAME = "{raw_name}"

    raw: RawEvent
{fields}

{transform_funcs}
    @staticmethod
    def build(raw):
{build_p1}

        return {name}(
            raw = RawEvent.build(raw),
{build_p2}
        )

    @property
    def eventTimestamp(self):
        return self.raw.timestamp

    @property
    def seqNum(self):
        return self.raw.seqNum

    @property
    def eventId(self):
        return self.ID

'''

def firstLower(text):
    if not text:
        return text
    return f'{text[0].lower()}{text[1:]}'

def eventNameFormat(text):
    if not text:
        return text
    return text.replace('_', ' ').title().replace(' ', '')

def fieldNameFormat(text):
    if not text or all([i.isupper() for i in text]):
        return text
    return firstLower(text.replace('_', ' ').title().replace(' ', '')).replace('raw', 'Raw')


def build_fields(event_def):
    ret = []
    for name, field in event_def["data"].items():
        suffix = 'Raw' if "transform" in field and name[-3:] != 'Raw' else ''
        f = f'{fieldNameFormat(name)}{suffix}: {TYPE_TO_PYOBJ[field["type"]]}'
        if "uom" in field:
            f += ' # ' + field['uom']
        ret.append(f)
    return '\n'.join([f'{" "*4}{f}' for f in ret])



def build_decode(event_def):
    p1s = []
    p2s = []
    for name, field in event_def["data"].items():
        p1 = f'{fieldNameFormat(name)}, = {unpack_command_for(field)}'
        p1s.append(p1)

        suffix = 'Raw' if "transform" in field and name[-3:] != 'Raw' else ''

        p2 = f'{fieldNameFormat(name)}{suffix} = {fieldNameFormat(name)},'
        p2s.append(p2)


    return '\n'.join([f'{" "*8}{f}' for f in p1s]), '\n'.join([f'{" "*12}{f}' for f in p2s])

def build_transform_funcs(event_def):
    try:
        from transforms import TRANSFORMS
    except ImportError:
        from .transforms import TRANSFORMS

    ret = []

    for name, field in event_def["data"].items():
        if not "transform" in field:
            continue

        for tx in field["transform"]:
            ret += TRANSFORMS[tx[0]](event_def, name, fieldNameFormat(name), field, tx[1])

    return '\n'.join([f'{" "*4}{f}' if f else '' for f in ret])

def build_event(event_id, event_def):
    return TEMPLATE.format(
        name = eventNameFormat(event_def["name"]),
        fields = build_fields(event_def),
        build_p1 = build_decode(event_def)[0],
        build_p2 = build_decode(event_def)[1],
        transform_funcs = build_transform_funcs(event_def),
        id = event_id,
        raw_name = event_def["name"]
    )

def build_events_map(events):
    ret = ['EVENT_IDS = {']
    for event_id, event_def in events.items():
        ret += [f'{" "*4}{event_id}: {eventNameFormat(event_def["name"])},']

    ret += ['}', '']

    ret += ['EVENT_NAMES = {']
    for event_id, event_def in events.items():
        ret += [f'{" "*4}"{event_def["name"]}": {eventNameFormat(event_def["name"])},']

    ret += ['}', '']

    return '\n'.join(ret)

if __name__ == '__main__':
    import json
    merged_events = {}

    output = f'{header}'
    with open("events.json", "r") as f:
        j = json.loads(f.read())
        merged_events.update(j["events"])

    with open("custom_events.json", "r") as f:
        j = json.loads(f.read())
        merged_events.update(j["events"])

    for event_id, event_def in merged_events.items():
        output += build_event(event_id, event_def)

    output += build_events_map(merged_events)


    print(output)
