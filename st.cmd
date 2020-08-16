#!/epics/iocs/postmortem/pure-elauncher/bin/linux-x86_64/scriptlaunch

#setup $SYS, $DELAY for each PM softIOC
< macro.cmd

epicsEnvSet("EPICS_CA_ADDR_LIST", "10.0.153.255")
epicsEnvSet("EPICS_CA_AUTO_ADDR_LIST", "NO")
#epicsEnvSet("PATH", "/opt/conda_envs/ap-2019-2.0/bin:$PATH")
epicsEnvSet("EPICS_BASE", "/usr/lib/epics")

cd "/epics/iocs/postmortem/pure-elauncher"
dbLoadDatabase("dbd/scriptlaunch.dbd",0,0)
scriptlaunch_registerRecordDeviceDriver(pdbbase)

#dbLoadRecords("$(EPICS_BASE)/db/iocAdminSoft.db", "IOC=SR-APHLA{IOC:PMRFCFD2}")
#dbLoadRecords ("$(EPICS_BASE)/db/save_restoreStatus.db", "P=SR-APHLA{IOC:PMRFCFD2}")
cd "/epics/iocs/postmortem/"
dbLoadRecords("pm.db", "SYS=$(SYS), DELAY=$(DELAY)")

cd $(TOP)
set_savefile_path("./as", "/save")
set_requestfile_path("./as", "/req")
set_pass0_restoreFile("settings_pass0.sav")
set_pass1_restoreFile("settings_pass1.sav")

iocInit()

makeAutosaveFileFromDbInfo("./as/req/settings_pass0.req", "autosaveFields_pass0")
create_monitor_set("settings_pass0.req", 30 , "")
makeAutosaveFileFromDbInfo("./as/req/settings_pass1.req", "autosaveFields_pass1")
create_monitor_set("settings_pass1.req", 30 , "")
