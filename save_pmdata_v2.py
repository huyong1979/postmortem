'''read PM configuration first, then read waveform PVs, 
then save all kinds of data to .h5 file.
Created on Aug. 12, 2020; @author: yhu
'''
import os
os.environ["EPICS_CA_MAX_ARRAY_BYTES"] = '200000000'
from pkg_resources import require
require('cothread')
import cothread
from cothread.catools import caget, caput, ca_nothing, FORMAT_TIME, DBR_CHAR_STR

import traceback
from datetime import datetime
import h5py
from pathlib import Path

import sys
import ConfigParser
import time

t_start = time.time()
op_status = "SR:AI-PM:ArchiverStatus-S" # status PV for operation
status = 0 # failed to save data if status = 3*n > 0 
waiting_time = 150 # wait (210-60)-second for circular buffer data ready 

def _caget(pvs, wait=120, **kargs):
    '''A wrapper of caget(): wait for 120-second, then give one more try if the 
    first caget fails'''
    try:
        return caget(pvs, **kargs)
    except:
        traceback.print_exc()
        cothread.Sleep(wait);
        return caget(pvs, throw=False, **kargs)


#11/28/2020: PS data were not saved with _caget_n(), meaning immediate another 
# caget after one failed caget seems not working well      
'''  
def _caget_n(pvs, n_try=5, **kargs):
    #A wrapper of caget(): try multiple times of caget if it fails
    if sys.version_info < (3,):
        pv_string_types = (str, unicode)
    else:
        pv_string_types = str

    for i in range(n_try):
        values = caget(pvs, throw=False, **kargs)
        if isinstance(pvs, pv_string_types): # pvs: single PV
            if values.ok:
                return values
            else:
                print("%s: failed to get the single PV %s"%(datetime.now(), pvs))
        else: # pvs: a list of PVs
            if all(value.ok for value in values):
                return values
            for value in values: 
                if not value.ok:
                    print("%s: failed to get %s"%(datetime.now(), value.name))

    return ca_nothing
'''                    
    
trigger_value = _caget('SR:C23-BI{BPM:10}PM:Status-I', format=FORMAT_TIME)
if ca_nothing == trigger_value:
    print("%s: failed to read trigger PV"%datetime.now())
    sys.exit()

trigger_ts = datetime.fromtimestamp(trigger_value.timestamp)
print("\n%s: beam dumped!"%str(trigger_ts))
caput(op_status, "Beam dumped! Wait ...", throw=False)
caput('SR-APHLA{PM}Program-Sts', 1, throw=False)
cothread.Sleep(waiting_time) # wait (210-60)-second for circular buffer data ready 


def read_conf(sub_sys):
    '''read sub_system PM configuration as a dictionary'''
    config = ConfigParser.ConfigParser()
    config.optionxform = str #keep keys as its original
    try:
        config.read(["/epics/iocs/postmortem/pm-" + sub_sys + ".conf"])
    except IOError:
        return None

    pmconfig_dict = {}
    sections = config.sections()
    for section in sections:
        pmconfig_dict[section] = dict(config.items(section))

    return pmconfig_dict


def get_filename(sub_sys):
    '''file format: /WFdata/WFdata/Y2020/M08/D12/RF-20200812-16:34:22.774905.h5'''    
    path = '/WFdata/WFdata'
    #path = '/epics/iocs/postmortem/WFdata'
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
    return file_name


# read and save PM data for each sub-system (ordered by data size) 
sub_systems = ['CBLM','BPM_FA','AI','BPM_TBT','PS','RF_CFC2','RF','RF_CFD2']
for sub_sys in sub_systems:
  status_pv = "SR-APHLA{" + sub_sys + "}PM:Status-Sts"
  error_pv =  "SR-APHLA{" + sub_sys + "}PM:ErrorMsg-Wf"
  filename_pv =  "SR-APHLA{" + sub_sys + "}PM:LastSavedFile-Wf"
  ca_timeout = _caget("SR-APHLA{" + sub_sys + "}PM:CATimeout-I") # 60-sec
  #ca_timeout = 120

  t0 = time.time()
  pmconfig_dict = read_conf(sub_sys)
  if not pmconfig_dict:  
    print("%s: no configuration file for %s"%(datetime.now(),sub_sys))
    continue

  print("%s: saving data for %s ..."%(datetime.now(), sub_sys))
  caput(status_pv, 1, throw=False) #"Started to read data ..."
  caput(op_status, "saving data for "+sub_sys, throw=False)

  try:
    file_name = get_filename(sub_sys)   
    hf = h5py.File(file_name, 'w')
    #the first standard group: Trigger 
    hf['Trigger/PV_names'] = str(pmconfig_dict["Trigger"]["pv"])
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
        pv_values = _caget(pv_names, timeout=ca_timeout, format=FORMAT_TIME)
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
        caput(status_pv, 2, throw=False) #"Started to write data ..."

    #the fifth standard group: Meta 
    hf['Meta/Nelems_perPV'] = nelems_perPV #nelems_perPV might not be accurate
    hf['Meta/Num_PVs'] = n_pvs

    #special group 'PV_StopAddr' for BPM-TBT, BPM-FA
    try:
        pvlist_str = pmconfig_dict["PV_StopAddr"]["pvlist"]
        pv_names = [str(pv) for pv in pvlist_str.split()]
        hf['PV_StopAddr'] = _caget(pv_names)
    except:
        pass 

    hf.close()
    caput(status_pv, 0, throw=False) #"Done!
    caput(error_pv, "No error.", datatype=DBR_CHAR_STR, throw=False)
    caput(filename_pv, file_name,datatype=DBR_CHAR_STR, throw=False)
    totalT = time.time() - t0
    print("\tit takes %f seconds to read and write data for %s"%(totalT, sub_sys))
    caput("SR-APHLA{" + sub_sys + "}PM:RWTime-I", totalT, throw=False)
    caput(op_status, "data saved for "+sub_sys, throw=False)
  except:
    caput(status_pv, 3, throw=False) #"Failed!
    status += 3;
    caput(error_pv, traceback.format_exc(), datatype=DBR_CHAR_STR, throw=False)
    caput(op_status, "Failed to save data for "+sub_sys, throw=False)
    traceback.print_exc()

#save Bunch-by-Bunch Feedback (BBF) data 
t_bbf = time.time()
caput('SR-APHLA{BBF}PM:Status-Sts', 1, throw=False)
try:
    import subprocess
    subprocess.call(['python', 'bxb_pm.py'])
    caput(op_status, "data saved for BBF", throw=False)
    caput('SR-APHLA{BBF}PM:Status-Sts', 0, throw=False)
    totalT_bbf = time.time() - t_bbf
    print("\tit takes %f seconds to read and write data for BBF"%totalT_bbf)
    caput("SR-APHLA{BBF}PM:RWTime-I", totalT_bbf, throw=False)
except:
    status += 3;
    caput(op_status, "Failed to save data for BBF", throw=False)
    caput('SR-APHLA{BBF}PM:Status-Sts', 3, throw=False)
    traceback.print_exc() 

cothread.Sleep(1)     
caput(op_status, "Done.", throw=False)
caput('SR-APHLA{PM}Status-Sts', int(status/3), throw=False)
loop_time = time.time() - t_start
print("\nTotal time (%d-sec-waiting): %f seconds"%(waiting_time, loop_time))
caput('SR-APHLA{PM}LoopTime-I', loop_time, throw=False)
caput('SR-APHLA{PM}Program-Sts', 0, throw=False)
