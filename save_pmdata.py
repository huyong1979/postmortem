'''read PM configuration first, then read waveform PVs, 
then save all kinds of data to .h5 file.
Created on Aug. 12, 2020; @author: yhu
'''

import sys
if len(sys.argv) != 2:
    print("You have to give a sub-system name, e.g.: python %s RF"%sys.argv[0])
    sys.exit()
sub_sys = sys.argv[1]

import time
t0 = time.time()

import os
os.environ["EPICS_CA_MAX_ARRAY_BYTES"] = '200000000'
from pkg_resources import require
require('cothread')
from cothread.catools import caget, FORMAT_TIME

import traceback
from datetime import datetime
import h5py
from pathlib import Path
import pmconfig 
pmconfig_dict = pmconfig.get_pmconfig()

#we can use "caput SR-APHLA{RF-CFD2}PM-Cmd.PROC 1" to test this script
test_pv = "SR-APHLA{" + sub_sys + "}PM:TestEnabled-Cmd"
test_enabled = caget(test_pv) #0: NO; 1: YES
trigger_pvname = str(pmconfig_dict["Trigger"]["pv"])
trigger_value = caget(trigger_pvname, format=FORMAT_TIME)#0: PM Detected
if test_enabled == 0 and trigger_value == 1:
    print("Error: someone has already reset PM before data were saved")
    sys.exit()
trigger_ts = datetime.fromtimestamp(trigger_value.timestamp)
print("\n%s: beam dumped!"%str(trigger_ts))#2020-08-14 20:56:41.355014: beam dumped!
print("%s: %d-sec later, start to save data ..."%(datetime.now(),time.time()-trigger_value.timestamp))

#.h5 is saved either in /WFdata/WFdata or the current IOC directory /epics/iocs/IOCNAME
#file format: /WFdata/WFdata/Y2020/M08/D12/RF-20200812-16:34:22.774905.h5
path = '/WFdata/WFdata/'
if not os.path.isdir(path):
    print("%s seems not available, so use the current working directory"%path)
    path = './'
year = str(time.strftime("%Y"))
mon = str(time.strftime("%m"))
day = str(time.strftime("%d"))
path = path + 'Y' + year + '/M' + mon + '/D' + day + '/' 
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
        pv_values = caget(pv_names, timeout=50, format=FORMAT_TIME)
        n_pvs += len(pv_values)
        nelems_perPV = len(pv_values[0])
        pv_timestamps = [str(datetime.fromtimestamp(pv_value.timestamp)) 
                            for pv_value in pv_values]

        g_pvnames.create_dataset(str(pv_group), data=pv_names)
        g_pvtimestamp.create_dataset(str(pv_group), data=pv_timestamps)
        g_wfdata.create_dataset(str(pv_group), data=pv_values)

    #the fifth standard group: Meta 
    hf['Meta/Nelems_perPV'] = nelems_perPV
    hf['Meta/Num_PVs'] = n_pvs

    hf.close()
    print("%s: successfully saved data to %s"%(datetime.now(), file_name))
    t1 = time.time()
    print("it takes %f seconds to read and write data to a file"%(t1-t0))
except:
    print("%s: something wrong occurred: "%datetime.now())
    traceback.print_exc()
    sys.exit()
