#!/epics/iocs/pm-RF/pure-elauncher/bin/linux-x86_64/scriptlaunch

epicsEnvSet("EPICS_CA_ADDR_LIST", "10.0.153.255")
epicsEnvSet("EPICS_CA_AUTO_ADDR_LIST", "NO")
#epicsEnvSet("PATH", "/opt/conda_envs/ap-2019-2.0/bin:$PATH")
epicsEnvSet("EPICS_BASE", "/usr/lib/epics")

cd "/epics/iocs/pm-RF/pure-elauncher"
dbLoadDatabase("dbd/scriptlaunch.dbd",0,0)
scriptlaunch_registerRecordDeviceDriver(pdbbase)

#dbLoadRecords("$(EPICS_BASE)/db/iocAdminSoft.db", "IOC=SR-APHLA{IOC:PMRF}")
#dbLoadRecords ("$(EPICS_BASE)/db/save_restoreStatus.db", "P=SR-APHLA{IOC:PMRF}")
cd "/epics/iocs/pm-RF/"
dbLoadRecords("pm.db")

iocInit()


