from __future__ import print_function

import os
import numpy as np
import time
import datetime
import h5py

os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '100000000'
# This change must happen before loading cothread.catools module.

from cothread.catools import caget, caput, camonitor, FORMAT_CTRL
from cothread import EventQueue

#----------------------------------------------------------------------
def get_output_filepath(prm, file_type):
    """"""

    #output_filename = '{0}_{1}_{2}.hdf5'.format(prm.sys, file_type, prm.tm)
    output_filename = '{0}_{1}_{2}.hdf5'.format(prm.sys, file_type, prm.tm.replace(':', ''))
    if os.path.exists('/WFdata'):
        #yr, mo, dd = prm.tm.split('T')[0].split('-')
        _date_str = prm.tm.split('-')[0]
        yr = _date_str[:4]
        mo = _date_str[4:6]
        dd = _date_str[6:]
        output_dirpath = '/WFdata/WFdata/Y{0}/M{1}/D{2}'.format(yr, mo, dd)
    else:
        output_dirpath = ''
    output_filepath = os.path.join(output_dirpath, output_filename)

    return output_filepath

########################################################################
class PRM:
    """"""

    #----------------------------------------------------------------------
    def __init__(self, sys, machine_name):
        """Constructor"""

        self.dcct = None

        if machine_name == 'nsls2sr':

            self.root = 'IGPF'

            self.dcct = 'SR:C03-BI{DCCT:1}I:Total-I'

        else:
            raise ValueError()

        self.debug = 1

        self.sys = sys

        self.tm = None

        self.fpga_rev = None

        self.acq_unit = None

        self.gpio_sel = None

        self.total_turns_pv = 'IGPF:{0}:SRAM:ACQ:TURNS'.format(sys)
        # ^ Contains the total number of turns
        self.post_trig_turns_pv = 'IGPF:{0}:SRAM:POST:TURNS'.format(sys)
        # ^ Contains the number of turns after the trigger

        self.total_turns = None
        self.post_trig_turns = None

    #----------------------------------------------------------------------
    def saveHDF5(self):
        """"""

        output_filepath = get_output_filepath(self, 'prm')

        f = h5py.File(output_filepath, 'w')
        for k in dir(self):
            v = getattr(self, k)
            if k.startswith('__') or callable(v): continue
            try:
                f.create_dataset(k, data=v, compression='gzip')
            except:
                f[k] = v
        f.close()

        print('* Data saved at [{0}]'.format(os.path.abspath(output_filepath)))

#----------------------------------------------------------------------
def getCurrentLocalTimeStr():
    """"""

    return time.strftime('%Y-%m-%dT%H-%M-%S', time.localtime())

#----------------------------------------------------------------------
def _event_queue_signal(value, index, event_queue):
    """"""

    return event_queue.Signal((value, index))

#----------------------------------------------------------------------
def iGp_read(sys, acq_unit, machine_name):
    """"""

    prm = PRM(sys, machine_name)

    prm.fpga_rev = caget('{0}:{1}:REVISION'.format(prm.root, prm.sys))

    if prm.fpga_rev >= 3.04:
        prm.acq_unit = acq_unit

    #prm.tm = getCurrentLocalTimeStr()

    # Get the PM trigger timestamp
    timestamp = caget('SR:C23-BI{BPM:10}PM:Time-SI')
    time_fmt = '%m/%d/%Y,%H:%M:%S'
    timeobj = time.strptime(timestamp.strip(), time_fmt)
    prm.tm = time.strftime('%Y%m%d-%H:%M:%S', timeobj)

    output_filepath = get_output_filepath(prm, 'gd')
    if os.path.exists(output_filepath):
        # It appears that the requested BxB PM data have been already
        # downloaded. So, this download/save request is ignored.
        return None, prm

    #os.mkdir(prm.tm)

    status = iGp_gd(prm)

    return status, prm

#----------------------------------------------------------------------
def iGp_gd(prm):
    """"""

    t00 = time.time()

    pvnm = '{0}:{1}:'.format(prm.root, prm.sys)

    prm.gpio_sel = caget(pvnm + 'GPIO_SEL')

    # Read out various parameters
    prm.when = getCurrentLocalTimeStr()

    pv_suffixes = ['CSET0', 'CSET1', 'CR256', 'DELAY'] # 1, 2, 3, 4
    if prm.fpga_rev < 3:
        pv_suffixes += ['GDLEN', 'WRT:HOLDOFF'] # 5, 6
    elif prm.fpga_rev < 3.04:
        pv_suffixes += ['GDTIME', 'HOLDTIME']
    else:
        pv_suffixes += [prm.acq_unit + ':GDTIME', prm.acq_unit + ':HOLDTIME']
    pv_suffixes += ['RF_FREQ', 'HARM_NUM'] # 7, 8
    if prm.fpga_rev < 3:
        pv_suffixes += ['REC_DS'] # 9
    elif prm.fpga_rev < 3.04:
        pv_suffixes += ['REC_DS']
    else:
        pv_suffixes += [prm.acq_unit + ':REC_DS']
    pv_suffixes += ['PROC_DS'] # 10
    if prm.gpio_sel == 1:
        pv_suffixes += ['FE_ATTEN', 'BE_ATTEN'] # 11, 12

    # Front-back end handling, separated from normal code
    if prm.fpga_rev < 2.04: # iGp8 before FBE-LT support
        if prm.gpio_sel == 1:
            pv_suffixes += ['WRT:FE_PHASE', 'WRT:BE_PHASE'] # 13, 14
    elif (prm.fpga_rev >= 3.00) and (prm.fpga_rev < 3.04): # Early iGp12
        if prm.gpio_sel == 1:
            pv_suffixes += ['FE_PHASE', 'BE_PHASE'] # 13, 14
        elif prm.gpio_sel == 2:
            pv_suffixes += [
                'FBE:Z_ATT', 'FBE:BE_ATT', 'FBE:Z_PHASE', 'FBE:BE_PHASE',
                'FBE:X_ATT', 'FBE:Y_ATT', 'FBE:X_PHASE', 'FBE:Y_PHASE'] # 11-18
    else: # iGp12 and late iGp8 with FBE-LT support
        if prm.gpio_sel == 1:
            pv_suffixes += ['FE_PHASE', 'BE_PHASE'] # 13, 14
        elif prm.gpio_sel == 2:
            pv_suffixes += [
                'FBE:Z_ATT', 'FBE:BE_ATT', 'FBE:Z_PHASE', 'FBE:BE_PHASE',
                'FBE:X_ATT', 'FBE:Y_ATT', 'FBE:X_PHASE', 'FBE:Y_PHASE'] # 11-18

    if prm.fpga_rev >= 3.04:
        pv_suffixes += [prm.acq_unit + ':POSTTIME']

    pv_list = [pvnm + _suf for _suf in pv_suffixes]

    pv_list += [prm.total_turns_pv, prm.post_trig_turns_pv]
    # ^ The added PVs contain the values for the total number of acquired turns,
    #   i.e., the full buffer size, and the number of turns after the trigger is
    #   received.

    # if dcct field is defined, use it as beam current PV
    if prm.dcct is not None:
        pv_list += [prm.dcct]

    # Read the channels
    data = caget(pv_list)

    # Parse the data
    prm.coeff0     = data[0] / 32768.0
    prm.coeff1     = data[1] / 32768.0
    prm.Nc         = len(prm.coeff0)
    prm.shift_gain = (int(data[2]) >> 4) & 7
    prm.delay      = data[3]
    prm.setsel     = (int(data[2]) >> 2) & 1
    prm.rf_freq    = data[6]
    prm.ring_size  = data[7]
    prm.ds         = data[8]
    prm.proc_ds    = data[9]

    if prm.fpga_rev >= 3.04:
        if prm.acq_unit == 'SRAM':
            time_unit = 1e3
        else:
            time_unit = 1.0

    if prm.fpga_rev < 3.0:
        prm.gdlen   = data[4]
        prm.holdoff = data[5]
    else:
        prm.gdlen   = data[4] / (prm.ds / prm.rf_freq) * time_unit
        prm.holdoff = data[5] / (prm.ds / prm.rf_freq) * time_unit

    # New data acquisition code, pre/post trigger
    if prm.fpga_rev >= 3.04:
        prm.post_trigger = data[-2] / (prm.ds / prm.rf_freq) * time_unit
        gden = caget(pvnm + 'GDEN')
        if prm.acq_unit == gden:
            prm.gden = 1
        else:
            prm.gden = 0
    else:
        prm.gden = (data[2] >> 8) & 1

    if prm.gpio_sel == 1:
        prm.fe_atten = data[10]
        prm.be_atten = data[11]
        prm.fe_phase = data[12]
        prm.be_phase = data[13]
    elif prm.gpio_sel == 2:
        prm.fe_atten = data[10]
        prm.be_atten = data[11]
        prm.fe_phase = data[12]
        prm.be_phase = data[13]
        prm.x_atten  = data[14]
        prm.y_atten  = data[15]
        prm.x_phase  = data[16]
        prm.y_phase  = data[17]

    prm.total_turns, prm.post_trig_turns = data[-3:-1]

    # If beam current PV is defined above, read out the current
    if prm.dcct is not None:
        prm.Io = data[-1]
    else:
        prm.Io = 0.0

    pv_list = [pvnm + 'DESC:CSET0', pvnm + 'DESC:CSET1']
    if prm.fpga_rev >= 3.04:
        if prm.fpga_rev >= 3.15:
            pv_list += [pvnm + prm.acq_unit + ':HWTEN']
        else:
            pv_list += [pvnm + prm.acq_unit + ':EXTEN']
        if prm.fpga_rev >= 3.05:
            pv_list += [pvnm + prm.acq_unit + ':POSTSEL']
    else:
        pv_list += [pvnm + 'EXTEN']
    if prm.fpga_rev >= 3.15:
        pv_list += [pvnm + prm.acq_unit + ':TRIG_IN_SEL']
    desc = caget(pv_list, format=FORMAT_CTRL)

    prm.cset0 = desc[0]
    prm.cset1 = desc[1]
    prm.exten = desc[2].enums[desc[2]]
    if prm.fpga_rev >= 3.05:
        prm.postsel = desc[3].enums[desc[3]]
    if prm.fpga_rev >= 3.15:
        prm.trig_src = desc[4].enums[desc[4]]

    if prm.debug:
        t01 = time.time()
        print('Parameters acquired after {0:.6f} seconds'.format(t01 - t00))

    if prm.acq_unit is not None:
        prm.data = get_data(pvnm, acq_unit=prm.acq_unit)
    else:
        prm.data = get_data(pvnm)

    if prm.postsel is not None:
        if prm.postsel == 1:
            prm.post_trigger = len(prm.data)

    if prm.debug:
        t02 = time.time()
        print('Data transferred after {0:.6f} seconds'.format(t02 - t00))

    prm.st = '{0}; I_0 = {1:.3f} mA; {2}'.format(prm.sys, prm.Io, prm.when)

    # Save gd.hdf5 file
    prm2gd(prm)

    # Save prm.hdf5 file
    prm.saveHDF5()

    status = 1

    return status

#----------------------------------------------------------------------
def prm2gd(prm):
    """"""

    M = int(np.floor(len(prm.data) / float(prm.ring_size)))

    bunches = np.zeros((M+1, prm.ring_size))
    bunches[0,:] = range(prm.ring_size)
    #bunches[1:,:] = prm.data[:(M * prm.ring_size)].reshape((prm.ring_size, M)).T
    bunches[1:,:] = prm.data[:(M * prm.ring_size)].reshape((M, prm.ring_size))

    output_filepath = get_output_filepath(prm, 'gd')

    f = h5py.File(output_filepath, 'w')
    f.create_dataset('bunches', data=bunches, compression='gzip')
    f['ring_size'] = prm.ring_size
    f['rf_freq'] = prm.rf_freq
    f['shift_gain'] = prm.shift_gain
    f['downsamp'] = prm.ds
    if prm.gden == 1:
        damp_brkpt = int(np.round(prm.gdlen / len(prm.data) * 63))
    else:
        damp_brkpt = 1
    f['damp_brkpt'] = damp_brkpt
    f['beamCurrent'] = prm.Io
    f.create_dataset('turn_offsets', data=np.zeros((prm.ring_size, 1)),
                     compression='gzip')
    scope = 2
    f['scope'] = scope
    f['total_turns'] = prm.total_turns
    f['post_trig_turns'] = prm.post_trig_turns
    f.close()

    print('* Data saved at [{0}]'.format(os.path.abspath(output_filepath)))

#----------------------------------------------------------------------
def get_data(pvroot, acq_unit=None):
    """"""

    fpga_rev = caget(pvroot + 'REVISION')

    if acq_unit is None:
        acq_unit = 'BRAM' # Default to BRAM for quicker transfers

    if fpga_rev > 10.0:
        # iGp12HF
        caput(pvroot + acq_unit + ':DUMP', 1, wait=True)
        while True:
            x = caget(pvroot + acq_unit + ':DUMP')
            if x == 0:
                break
            time.sleep(0.01)
        n = caget(pvroot + acq_unit + ':RAW:SAMPLES')
        x = caget(pvroot + acq_unit + ':RAW')
    elif fpga_rev >= 3.04:
        # Completely new model!!!

        # Redone in 2017 to monitor ACQ_ID
        aid = pvroot + acq_unit + ':RAW:ACQ_ID'

        evq = EventQueue()

        camon_dict = dict(evq=evq)

        subs = camonitor([aid],
            lambda val, ind, event_queue=evq:
            _event_queue_signal(val, ind, event_queue))

        nSubs = len(subs)

        ready_index_list = []
        while True:
            try:
                init_data, index = evq.Wait(timeout=1.0) # initial data update
            except:
                print('\n***### WARNING ###***')
                print(('Event queue wait for initial transient '
                      'signal exceeded specified timeout'))
                break

            ready_index_list.append(index)
            if len(ready_index_list) == nSubs:
                break

        print('Init ACQ ID = {0:d}'.format(init_data))

        # Trigger dump
        caput(pvroot + acq_unit + ':DUMP', 1, wait=True)

        # Wait for acquisition ID to update
        success_msg = '* Transient states are over.'

        while True:
            try:
                new_data, index = evq.Wait(timeout=10.0)
                print(success_msg)
            except:
                print('\n***### WARNING ###***')
                print(('Event queue wait for updated transient '
                       'signal exceeded specified timeout.'))
                print(('The specified setpoints may have been already at or '
                       'very close to the current setpoints, which may have\n'
                       'made none of the transient monitoring PVs change into '
                       '"transient" states.'))
            break

        # Close all the camonitor instances
        for sub in subs: sub.close()

        #print('new_data', new_data)

        _id = caget(aid)

        print('New ACQ ID = {0:d}'.format(_id))

        n = caget(pvroot + acq_unit + ':RAW:SAMPLES')
        x = caget(pvroot + acq_unit + ':RAW')
    else:
        raise NotImplementedError()

        # Save the data
        caput(pvroot + 'DATARD', 1, wait=True)
        caput(pvroot + 'DATARD', 0, wait=True)
        ip = caget(pvroot + 'IP_ADDR')

    return x

if __name__ == '__main__':

    acq_unit = 'SRAM'
    machine_name = 'nsls2sr'

    for sys_name in ['TransFBX', 'TransFBY', 'TransFBZ']:

        status, prm = iGp_read(sys_name, acq_unit, machine_name)

        if status is None:

            print(
                ('\n* Requested BxB Post-Mortem data ({0} [{1}]) appear to have been '
                 'previously downloaded and saved. So, this request is ignored.')
                .format(sys_name, prm.tm))

            continue

        print('\n* BxB Post-Mortem data ({0}) have been successfully saved, now re-arming...'
              .format(sys_name))

        caput('{0}:{1}:{2}:ARM'.format(prm.root, sys_name, acq_unit), 1, wait=True)

    print('\n** Finished. **')
