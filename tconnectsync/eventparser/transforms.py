import json
try:
    from static_dicts import ALERTS_DICT, ALARMS_DICT, CGM_ALERTS_DICT
except ImportError:
    from .static_dicts import ALERTS_DICT, ALARMS_DICT, CGM_ALERTS_DICT

def enumNameFormat(text):
    if not text:
        return text
    t = text.replace('_', ' ').title().replace(' ', '')
    if t.startswith('no,'):
        return 'No'
    if t.startswith('yes,'):
        return 'Yes'

    rem = None
    for i in '-,.':
        spl = t.split(i)
        t = spl[0]
        if len(spl) > 1:
            rem = rem or spl[1]

    for i in '()/"\u201c\u201d':
        t = t.replace(i, '')

    if t.lower() == 'false':
        return 'FalseVal'
    if t.lower() == 'true':
        return 'TrueVal'
    if t.lower() == 'none':
        return 'NoneVal'
    if t.lower() == 'reserved':
        return None
    if t.lower() == 'unused':
        return None
    if t.lower() == 'unavailable' and rem:
        suffix = enumNameFormat(rem)
        t += f'{suffix[0].lower()}{suffix[1:]}'

    return f'{t[0].upper()}{t[1:]}'

def transform_enum(event_def, name, name_fmt, field, tx):
    out = []
    lines_for_out = json.dumps(tx, indent=4).splitlines()
    out += [f'{enumNameFormat(name_fmt)}Map = {lines_for_out[0]}']
    out += lines_for_out[1:]
    out += ['']
    out += [f'class {enumNameFormat(name_fmt)}Enum(Enum):']
    out += [
        f'    {enumNameFormat(v)} = {k}' for k, v in tx.items() if enumNameFormat(v)
    ]
    out += ['']
    out += [
        '@property',
        f'def {name_fmt}(self):',
        f'    try:',
        f'        return self.{enumNameFormat(name_fmt)}Enum(self.{name_fmt}Raw)',
        f'    except ValueError as e:',
        f'        logger.error("Invalid {name_fmt}Raw in {enumNameFormat(name_fmt)} for "+str(self))',
        f'        logger.error(e)',
        f'        return None',
        ''
    ]

    return out

def transform_dictionary(event_def, name, name_fmt, field, tx):
    if tx == 'alerts':
        return transform_enum(event_def, name, name_fmt, field, ALERTS_DICT)

    if tx == 'alarms':
        return transform_enum(event_def, name, name_fmt, field, ALARMS_DICT)

    if tx == 'dalerts':
        return transform_enum(event_def, name, name_fmt, field, CGM_ALERTS_DICT)
    return [f'# Dictionary unknown: {tx}']

def transform_bitmask(event_def, name, name_fmt, field, tx):
    out = []
    lines_for_out = json.dumps(tx, indent=4).splitlines()
    out += [f'{enumNameFormat(name_fmt)}Map = {lines_for_out[0]}']
    out += lines_for_out[1:]
    out += ['']
    out += [f'class {enumNameFormat(name_fmt)}Bitmask(IntFlag):',]
    out += [
        f'    {enumNameFormat(v)} = 2**{k}' for k, v in tx.items() if enumNameFormat(v)
    ]
    out += ['']
    out += [
        '@property',
        f'def {name_fmt}(self):',
        f'    try:',
        f'        return self.{enumNameFormat(name_fmt)}Bitmask(self.{name_fmt}Raw)',
        f'    except ValueError as e:',
        f'        logger.error("Invalid {name_fmt}Raw in {enumNameFormat(name_fmt)}Bitmask for "+str(self))',
        f'        logger.error(e)',
        f'        return None',
        f''
    ]

    return out

def transform_ratio(event_def, name, name_fmt, field, tx):
    out = []
    out += [
        '@property',
        f'def {name_fmt}(self):',
        f'    return self.{name_fmt}Raw * {tx}',
        ''
    ]

    return out

def transform_battery_charge_percent(event_def, name, name_fmt, field, tx):
    out = []
    out += [
        '@property',
        f'def batteryChargePercent(self):',
        f'    return (256*(self.batterychargepercentmsbRaw-14)+self.batterychargepercentlsbRaw)/(3*256)',
        ''
    ]

    return out


TRANSFORMS = {
    'enum': transform_enum,
    'dictionary': transform_dictionary,
    'bitmask': transform_bitmask,
    'ratio': transform_ratio,
    'battery_charge_percent': transform_battery_charge_percent
}