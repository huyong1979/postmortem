'''read PM configuration first, then read waveform PVs, 
then save all kinds of data to .h5 file.
Created on Aug. 12, 2020; @author: yhu
'''
import sys, os, time
if len(sys.argv) != 2:
    print("You have to give a sub-system name, e.g.: python %s RF"%sys.argv[0])
    sys.exit()
sub_sys = str(sys.argv[1])

from datetime import datetime
from pathlib import Path

print("\n%s: beam dumped! (version 1)"%str(datetime.now()))

path = '/WFdata/WFdata'
if not os.path.isdir(path):
    print("%s seems not available, so use the current working directory"%path)
    path = os.popen('pwd').read().strip()

year = str(time.strftime("%Y"))
mon = str(time.strftime("%m"))
day = str(time.strftime("%d"))
path = path + '/Y' + year + '/M' + mon + '/D' + day + '/' 
if not os.path.isdir(path):
    print("the directory %s seems not existing, so creating one ..."%path)
    new_dir = Path(path)
    new_dir.mkdir(parents=True)   

ts_format = "%Y%m%d-%H:%M:%S.%f"
file_name = path + sub_sys + '-' + str(datetime.now()) + ".txt"
fd = open(file_name, 'w')
fd.write("test")
fd.close()
sys.exit()

#11/18/2020: this version is retired; save_pmdata_v2.py is in use
import sys
if len(sys.argv) != 2:
    print("You have to give a sub-system name, e.g.: python %s RF"%sys.argv[0])
    sys.exit()
sub_sys = str(sys.argv[1])

#read sub_system PM configuration as a dictionary
import ConfigParser
config = ConfigParser.ConfigParser()
config.optionxform = str #keep keys as its original
try:
    config.read(["/epics/iocs/postmortem/pm-" + sub_sys + ".conf"])
except IOError:
    print("Error: no sub-system configuration file found")
    sys.exit() 

pmconfig_dict = {}
sections = config.sections()
for section in sections:
    pmconfig_dict[section] = dict(config.items(section))
#print(pmconfig_dict)

import time
t0 = time.time()

import os
os.environ["EPICS_CA_MAX_ARRAY_BYTES"] = '200000000'
from pkg_resources import require
require('cothread')
import cothread
from cothread.catools import caget, caput, FORMAT_TIME, DBR_CHAR_STR

import traceback
from datetime import datetime
import h5py
from pathlib import Path

#status = "SR:AI-PM:ArchiverStatus-S"
status_pv = "SR-APHLA{" + sub_sys + "}PM:Status-Sts"
error_pv =  "SR-APHLA{" + sub_sys + "}PM:ErrorMsg-Wf"
filename_pv =  "SR-APHLA{" + sub_sys + "}PM:LastSavedFile-Wf"
ca_timeout = caget("SR-APHLA{" + sub_sys + "}PM:CATimeout-I") # 60-sec

trigger_pvname = str(pmconfig_dict["Trigger"]["pv"])
trigger_value = caget(trigger_pvname, format=FORMAT_TIME)#0: PM Detected
trigger_ts = datetime.fromtimestamp(trigger_value.timestamp)
print("\n%s: beam dumped!"%str(trigger_ts))

caput(status_pv, 1) #"Started to read data ..."
#.h5 is saved either in /WFdata/WFdata or the current IOC directory /epics/iocs/IOCNAME
#file format: /WFdata/WFdata/Y2020/M08/D12/RF-20200812-16:34:22.774905.h5
path = '/WFdata/WFdata'
if not os.path.isdir(path):
    print("%s seems not available, so use the current working directory"%path)
    path = os.popen('pwd').read().strip()

year = str(time.strftime("%Y"))
mon = str(time.strftime("%m"))
day = str(time.strftime("%d"))
path = path + '/Y' + year + '/M' + mon + '/D' + day + '/' 
if not os.path.isdir(path):
    print("the directory %s seems not existing, so creating one ..."%path)
    new_dir = Path(path)
    new_dir.mkdir(parents=True)   

ts_format = "%Y%m%d-%H:%M:%S.%f"
file_name = path + sub_sys + '-' + trigger_ts.strftime(ts_format) + ".h5"

try:
    hf = h5py.File(file_name, 'w')
    #the first standard group: Trigger 
    hf['Trigger/PV_names'] = trigger_pvname
    hf['Trigger/Time_stamps'] = str(trigger_ts) # have to str(...)

    #another 3 groups: PV_Names, PV_TimeStamp, WFdata
    g_pvnames = hf.create_group('PV_Names')
    g_pvtimestamp = hf.create_group('PV_Timestamp')
    g_wfdata =  hf.create_group('WFdata')

    #for the fifth standard group: Meta
    n_pvs = 0
    nelems_perPV = 0

    for pv_group in pmconfig_dict["PV_Names"].keys():
        pvlist_str = pmconfig_dict["PV_Names"][pv_group]
        pv_names = [str(pv) for pv in pvlist_str.split()]
        #hf['PV_Names'/str(pv_group)] = pv_names
        #the default timeout=5 seems not working for big RF waveforms
        pv_values = caget(pv_names, timeout=ca_timeout, format=FORMAT_TIME)
        n_pvs += len(pv_values)

        try:
            #pv_values[0] could be a scalar value
            nelems_perPV = len(pv_values[0])
        except:    #TypeError: object of type 'ca_int' has no len()
            pass 

        pv_timestamps = [str(datetime.fromtimestamp(pv_value.timestamp)) 
                            for pv_value in pv_values]

        g_pvnames.create_dataset(str(pv_group), data=pv_names)
        g_pvtimestamp.create_dataset(str(pv_group), data=pv_timestamps)
        g_wfdata.create_dataset(str(pv_group), data=pv_values, compression='gzip')
        caput(status_pv, 2) #"Started to write data ..."

    #the fifth standard group: Meta 
    hf['Meta/Nelems_perPV'] = nelems_perPV #nelems_perPV might not be accurate
    hf['Meta/Num_PVs'] = n_pvs

    #special group 'PV_StopAddr' for BPM-TBT, BPM-FA
    try:
        pvlist_str = pmconfig_dict["PV_StopAddr"]["pvlist"]
        pv_names = [str(pv) for pv in pvlist_str.split()]
        hf['PV_StopAddr'] = caget(pv_names)
    except:
        pass 

    hf.close()
    caput(status_pv, 0) #"Done!
    caput(error_pv, "No error.", datatype=DBR_CHAR_STR)
    caput(filename_pv, file_name,datatype=DBR_CHAR_STR)
    totalT = time.time() - t0
    print("it takes %f seconds to read and write data to a file"%totalT)
    caput("SR-APHLA{" + sub_sys + "}PM:RWTime-I", totalT)
except:
    caput(status_pv, 3) #"Failed!
    caput(error_pv, traceback.format_exc(), datatype=DBR_CHAR_STR)
    traceback.print_exc()
    sys.exit()
