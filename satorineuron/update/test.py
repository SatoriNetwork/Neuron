r'''
docker run --rm -it --name satorineuron -p 127.0.0.1:24601:24601 -v c:\repos\Satori\Neuron\satorineuron\update:/Satori/Neuron/satorineuron/update --env ENV=prod --env RUNMODE=wallet satorinet/satorineuron:latest bash
docker run --rm -it --name satorineuron -p 127.0.0.1:24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Lib:/Satori/Lib --env-file c:\repos\Satori\Neuron\.env --env ENV=prod --env RUNMODE=normal satorinet/satorineuron:latest bash
'''
from satorineuron.update import entry
entry.hashes.getFolders()
entry.hashes.getTargets()
o, e = entry.pull.fromGithub('lib')
print(o.decode())
print(e.decode())
entry.hashes.getFolders()
entry.pull.fromGithub('engine')
