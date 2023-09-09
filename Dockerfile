# copy to and run from ../ or C:\repos\Satori
# (updating process is the only thing that requires git)
# (vim for troubleshooting)

# python:slim will eventually fail, if we need to revert try this:
# FROM python:slim3.12.0b1-slim
FROM python:slim

RUN apt-get update
RUN apt-get install -y build-essential
RUN apt-get install -y wget
RUN apt-get install -y git 
RUN apt-get install -y vim

RUN wget https://dist.ipfs.tech/kubo/v0.21.0/kubo_v0.21.0_linux-amd64.tar.gz
RUN tar -xvzf kubo_v0.21.0_linux-amd64.tar.gz
RUN cd kubo && bash install.sh
# has no effect, we put it in the run command
#RUN echo "IPFS_PATH=/SatoriNeuron/config/ipfs" >> /etc/environment
#RUN echo "source /etc/environment" >> ~/.bashrc 
# echo $IPFS_PATH
# RUN ipfs init # do not init. it will be initialized by the node, so that each container has a unique ID.

RUN mkdir /SatoriLib
RUN mkdir /SatoriEngine
RUN mkdir /SatoriWallet
RUN mkdir /SatoriNeuron
RUN mkdir /SatoriNeuron/data
RUN mkdir /SatoriNeuron/temp
RUN mkdir /SatoriNeuron/uploaded
RUN mkdir /SatoriNeuron/models
RUN mkdir /SatoriNeuron/predictions
RUN mkdir /SatoriNeuron/wallet
COPY Lib/satorilib /SatoriLib/satorilib
COPY Lib/setup.py /SatoriLib/setup.py
COPY Lib/requirements.txt /SatoriLib/requirements.txt
COPY Engine/satoriengine /SatoriEngine/satoriengine
COPY Engine/setup.py /SatoriEngine/setup.py
COPY Engine/requirements.txt /SatoriEngine/requirements.txt
COPY Wallet/satoriwallet /SatoriWallet/satoriwallet
COPY Wallet/reqs /SatoriWallet/reqs
COPY Wallet/setup.py /SatoriWallet/setup.py
COPY Wallet/requirements.txt /SatoriWallet/requirements.txt
COPY Node/satorineuron/ /SatoriNeuron/satorineuron/
COPY Node/config/config.yaml /SatoriNeuron/config/config.yaml
COPY Node/setup.py /SatoriNeuron/setup.py
COPY Node/requirements.txt /SatoriNeuron/requirements.txt

RUN chmod -R 777 /SatoriEngine
RUN chmod -R 777 /SatoriLib
RUN chmod -R 777 /SatoriWallet
RUN chmod -R 777 /SatoriNeuron

RUN cd /SatoriEngine && python setup.py develop
RUN cd /SatoriLib && python setup.py develop
RUN cd /SatoriWallet && python setup.py develop
RUN cd /SatoriNeuron && python setup.py develop

# satori ui
EXPOSE 24601 
# i don't remember what these are for... 
EXPOSE 3000

# ipfs web ui
EXPOSE 5002
# ipfs 
EXPOSE 4001 5001 23384

WORKDIR /SatoriNeuron/satorineuron/web

#ENTRYPOINT [ "python" ]
#CMD ["python", "./app.py" ]

# BUILD PROCESS:
# copy to and run from ../ (cd C:\repos\Satori)
# C:\repos\Satori> docker build --no-cache -t satorinet/satorineuron:v1 .
# docker push satorinet/satorineuron:v1
# description: Miner environment and software for the Satori Network

# RUN OPTIONS
# docker run --rm -it --name satorineuron -p 24601:24601 -p 24602:4001 -p 24603:5001 -p 24604:23384 -v c:\repos\Satori\Node:/SatoriNeuron -v c:\repos\Satori\Lib:/SatoriLib -v c:\repos\Satori\Wallet:/SatoriWallet -v c:\repos\Satori\Engine:/SatoriEngine -e IPFS_PATH=/SatoriNeuron/config/ipfs --env SATORI_RUN_MODE=dockerdev satorinet/satorineuron:v1 bash
# docker run --rm -it --name satorineuron -p 24601:24601 -p 24602:4001 -p 24603:5001 -p 24604:23384 -v c:\repos\Satori\Node:/SatoriNeuron -v c:\repos\Satori\Lib:/SatoriLib -v c:\repos\Satori\Wallet:/SatoriWallet -v c:\repos\Satori\Engine:/SatoriEngine -e IPFS_PATH=/SatoriNeuron/config/ipfs --env SATORI_RUN_MODE=prod satorinet/satorineuron:v1 ./start.sh
# docker exec -it satorineuron bash