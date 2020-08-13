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
print("saving data ...")

import os
os.environ["EPICS_CA_MAX_ARRAY_BYTES"] = '200000000'

from pkg_resources import require
require('cothread')
from cothread.catools import caget, FORMAT_TIME

from datetime import datetime
import h5py
from pathlib import Path

import pmconfig 
pmconfig_dict = pmconfig.get_pmconfig()

pvlist_str = pmconfig_dict["WFdata"]["pvlist"]
pv_names = [str(pv) for pv in pvlist_str.split()]
pv_values = caget(pv_names, timeout=50, format=FORMAT_TIME)
t1 = time.time()
print("it takes %f seconds to read %d waveforms"%((t1-t0), len(pv_names)))
pv_timestamps = [str(datetime.fromtimestamp(pv_value.timestamp)) 
                    for pv_value in pv_values]

bufftrigTS_pv = str(pmconfig_dict["BufferTS"]["pv"])
value = caget(bufftrigTS_pv, format=FORMAT_TIME)
bufftrigTS_val = str(datetime.fromtimestamp(value.timestamp))

nelems_perPV = int(caget(str(pv_names[0])+'.NELM'))
num_PVs = len(pv_names)

trigger_pvname = str(pmconfig_dict["Trigger"]["pv"])
value = caget(trigger_pvname, format=FORMAT_TIME)
trigger_ts = str(datetime.fromtimestamp(value.timestamp))

WFdata_key = "WFdata/" + sub_sys
keys = [
    'BufferTS/BuffTrigTS_PV',   'BufferTS/BuffTrigTS_Val', 
    'Meta/Nelems_perPV',        'Meta/Num_PVs',
    'PV_Names',                 'PV_TimeSamp',
    'Trigger/PV_names',         'Trigger/Time_stamps',
    WFdata_key]

values = [
    bufftrigTS_pv,      bufftrigTS_val, 
    nelems_perPV,       num_PVs,
    pv_names,           pv_timestamps, 
    trigger_pvname,     trigger_ts,
    pv_values]

#.h5 is saved either in /WFdata/WFdata or the current directory ./
#/WFdata/WFdata/Y2020/M08/D12/RF-20200812-16:34:22.774905.h5
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
file_name = path + sub_sys + '-' + datetime.now().strftime(ts_format) + ".h5"

hf = h5py.File(file_name, 'w')
for (key, value) in zip (keys, values):
    hf[key] = value
hf.close()

t2 = time.time()
print("it takes %f seconds to write data"%(t2-t1))
print("total time: %f seconds"%(t2-t0))
print("data saved to %s"%file_name)
