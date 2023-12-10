from satorineuron.structs.start import StartupDagStruct


start: StartupDagStruct = None


def setStart(variable):
    global start
    start = variable
