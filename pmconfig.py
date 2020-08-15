#!/usr/bin/python
'''Get sub-system configuration information for postmortem.
Created on Aug. 12, 2020; @author: yhu
'''

import os
import platform
import ConfigParser

def get_pmconfig():
    '''There should be a file named 'pm.conf' like this:
[BufferTS]
pv = 'SR-RF{CFC:D-RAM-Chan:0}Cmd:Time'

[Trigger]
pv = 'SR:C23-BI{BPM:10}PM:Status-I'

[WFdata]
pvlist =SR-RF{CFC:D-RAM-Chan:0}Val:I-I
	SR-RF{CFC:D-RAM-Chan:0}Val:Q-I
	SR-RF{CFC:D-RAM-Chan:1}Val:I-I
    '''
    if platform.system() == 'Windows':
        raise RuntimeError("Does not support Windows platform yet.")

    config = ConfigParser.ConfigParser()
    config.optionxform = str #keep keys as its original
    try:
        #user home directory settings will overwrite system config(/etc/...), 
        #system config will overwrite the config in the current working directory
        config.read([os.path.join(os.path.dirname(__file__), 'pm.conf'), 
                    'pm.conf', 
                    os.path.expanduser('/etc/pm/pm.conf'),
                    os.path.expanduser('~/.pm.conf')])
    except IOError:
        print("Error: no sub-system configuration file 'pm.conf' found")
        return {} 

    pmconfig = {}
    sections = config.sections()
    for section in sections:
        pmconfig[section] = dict(config.items(section))

    return pmconfig

if __name__ == "__main__":
    print(get_pmconfig())
