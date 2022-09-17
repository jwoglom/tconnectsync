#!/usr/bin/env python3

class Time:
    def __init__(self, hour: int, min: int):
        self.hour = hour
        self.min = min
    
    @classmethod
    def parse(cls, input):
        if ' ' not in input:
            raise ValueError('unable to parse time: %s' % input)

        hrmin, ampm = input.split(' ')
        
        hr, min = hrmin.split(':')
        hr = int(hr)
        min = int(min)

        if ampm.lower() == 'pm':
            hr += 12
        elif ampm.lower() != 'am':
            raise ValueError('unable to parse time: %s' % input)
        
        return cls(hr, min)