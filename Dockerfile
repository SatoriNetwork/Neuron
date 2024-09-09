# copy to and run from ../ or C:\repos\Satori
# (updating process is the only thing that requires git)
# (vim for troubleshooting)

# python:slim will eventually fail, if we need to revert try this:
# FROM python:slim3.12.0b1-slim
FROM python:3.9-slim AS builder

RUN apt-get update && \
    apt-get install -y build-essential wget git vim cmake zip && \
    mkdir /Satori && \
    cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Synapse.git && \
    cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Lib.git && \
    cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Wallet.git && \
    cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Engine.git && \
    cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Neuron.git && \
    mkdir /Satori/Neuron/models && \
    chmod -R 777 /Satori/Synapse && \
    chmod -R 777 /Satori/Lib && \
    chmod -R 777 /Satori/Wallet && \
    chmod -R 777 /Satori/Engine && \
    chmod -R 777 /Satori/Neuron && \
    pip install --upgrade pip && \
    cd /Satori/Synapse && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Lib && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Wallet && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Engine && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Neuron && pip install --no-cache-dir -r requirements.txt && python setup.py develop

    # larger version: add later.
    #cd /Satori && git clone https://github.com/amazon-science/chronos-forecasting.git && \
    #cd /Satori && git clone https://github.com/ibm-granite/granite-tsfm.git && \
    #pip install --no-cache-dir torch==2.3.1 && \
    #pip install --no-cache-dir transformers==4.41.2 && \
    #pip install --no-cache-dir /Satori/granite-tsfm && \
    #pip install --no-cache-dir /Satori/chronos-forecasting && \

# python-evrmorelib needs cmake and zip
# ipfs - unused
#RUN wget https://dist.ipfs.tech/kubo/v0.21.0/kubo_v0.21.0_linux-amd64.tar.gz
#RUN tar -xvzf kubo_v0.21.0_linux-amd64.tar.gz
#RUN cd kubo && bash install.sh

# has no effect, we put it in the run command
#RUN echo "IPFS_PATH=/Satori/Neuron/config/ipfs" >> /etc/environment
#RUN echo "source /etc/environment" >> ~/.bashrc
# echo $IPFS_PATH
# RUN ipfs init # do not init. it will be initialized by the node, so that each container has a unique ID.

# todo: maybe just move all this to the code part.

#RUN cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Synapse.git
#RUN cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Lib.git
#RUN cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Wallet.git
#RUN cd /Satori && git clone -b dev https://github.com/SatoriNetwork/Engine.git

# ADVANCED ENGINE STUFF
# RUN cd /Satori && git clone https://github.com/amazon-science/chronos-forecasting.git
# RUN cd /Satori && git clone https://github.com/ibm-granite/granite-tsfm.git
# RUN pip install --upgrade pip
# RUN pip install --no-cache-dir /Satori/granite-tsfm
# RUN pip install --no-cache-dir /Satori/chronos-forecasting

# COPY Synapse/satorisynapse /Satori/Synapse/satorisynapse
# COPY Synapse/setup.py /Satori/Synapse/setup.py
# COPY Synapse/requirements.txt /Satori/Synapse/requirements.txt
# COPY Lib/satorilib /Satori/Lib/satorilib
# COPY Lib/setup.py /Satori/Lib/setup.py
# COPY Lib/requirements.txt /Satori/Lib/requirements.txt
# COPY Wallet/satoriwallet /Satori/Wallet/satoriwallet
# COPY Wallet/reqs /Satori/Wallet/reqs
# COPY Wallet/setup.py /Satori/Wallet/setup.py
# COPY Wallet/requirements.txt /Satori/Wallet/requirements.txt
# COPY Engine/satoriengine /Satori/Engine/satoriengine
# COPY Engine/setup.py /Satori/Engine/setup.py
# COPY Engine/requirements.txt /Satori/Engine/requirements.txt
# COPY Neuron/satorineuron/ /Satori/Neuron/satorineuron/
# COPY Neuron/config/config.yaml /Satori/Neuron/config/config.yaml
# COPY Neuron/setup.py /Satori/Neuron/setup.py
# COPY Neuron/requirements.txt /Satori/Neuron/requirements.txt


## no need for ollama at this time.
#RUN apt-get install -y curl
#RUN mkdir /Satori/Neuron/chat
#RUN cd /Satori/Neuron/chat && curl -fsSL https://ollama.com/install.sh | sh
#RUN ollama serve
#RUN ollama pull llama3

# satori ui
EXPOSE 24601

# ipfs web ui
#EXPOSE 5002
# ipfs
#EXPOSE 4001 5001 23384
#EXPOSE 3000

WORKDIR /Satori/Neuron/satorineuron/web

#ENTRYPOINT [ "python" ]
#CMD ["python", "./app.py" ]

# BUILD PROCESS:
# \Satori> docker buildx build --no-cache -f "Neuron/Dockerfile" --platform linux/amd64,linux/arm64 -t satorinet/satorineuron:latest .
# \Satori> docker buildx build -f "Neuron/Dockerfile" --platform linux/amd64 -t satorinet/satorineuron:latest --load .
# \Satori> docker buildx build -f "Neuron/Dockerfile" --platform linux/arm64 -t satorinet/satorineuron:latest --load .
# \Satori> docker push satorinet/satorineuron:latest

# BUILD-PUSH PROCESS:
# copy to and run from ../ (cd ..)
# \Satori> docker build --no-cache -f "Neuron/Dockerfile base" -t satorinet/satorineuron:base .
# OR
# \Satori> docker buildx create --use
# \Satori> docker buildx build -f "Neuron/Dockerfile base" --platform linux/amd64,linux/arm64 -t satorinet/satorineuron:base --load .
# delete the base one after you push it, we just need it local

# RUN OPTIONS
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine -e IPFS_PATH=/Satori/Neuron/config/ipfs --env ENV=local satorinet/satorineuron:base bash
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine -e IPFS_PATH=/Satori/Neuron/config/ipfs --env ENV=prod satorinet/satorineuron:base ./start.sh
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse  -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine satorinet/satorineuron:base bash
# docker run --rm -it --name satorineuron satorinet/satorineuron:base bash
# docker exec -it satorineuron bash


FROM builder AS builder1

# copy to and run from ../ or C:\repos\Satori
# (updating process is the only thing that requires git)
# (vim for troubleshooting)

# FROM satorinet/satorineuron:base

#RUN cd / && rm -rf /Satori && mkdir /Satori && mkdir /Satori/Synapse && mkdir /Satori/Lib && mkdir /Satori/Wallet && mkdir /Satori/Engine && mkdir /Satori/Neuron && mkdir /Satori/Neuron/data && mkdir /Satori/Neuron/uploaded && mkdir /Satori/Neuron/models && mkdir /Satori/Neuron/predictions && mkdir /Satori/Neuron/wallet
COPY Synapse/satorisynapse /Satori/Synapse/satorisynapse
COPY Synapse/setup.py /Satori/Synapse/setup.py
COPY Synapse/requirements.txt /Satori/Synapse/requirements.txt
COPY Lib/satorilib /Satori/Lib/satorilib
COPY Lib/setup.py /Satori/Lib/setup.py
COPY Lib/requirements.txt /Satori/Lib/requirements.txt
COPY Wallet/satoriwallet /Satori/Wallet/satoriwallet
COPY Wallet/reqs /Satori/Wallet/reqs
COPY Wallet/setup.py /Satori/Wallet/setup.py
COPY Wallet/requirements.txt /Satori/Wallet/requirements.txt
COPY Engine/satoriengine /Satori/Engine/satoriengine
COPY Engine/setup.py /Satori/Engine/setup.py
COPY Engine/requirements.txt /Satori/Engine/requirements.txt
COPY Neuron/satorineuron/ /Satori/Neuron/satorineuron/
#COPY Neuron/config/config.yaml /Satori/Neuron/config/config.yaml
COPY Neuron/setup.py /Satori/Neuron/setup.py
COPY Neuron/requirements.txt /Satori/Neuron/requirements.txt

RUN chmod -R 777 /Satori/Synapse && \
    chmod -R 777 /Satori/Lib && \
    chmod -R 777 /Satori/Wallet && \
    chmod -R 777 /Satori/Engine && \
    chmod -R 777 /Satori/Neuron

RUN apt-get update && apt-get install -y dos2unix && dos2unix start.sh && dos2unix start_from_image.sh

# satori ui
EXPOSE 24601

ENV IPFS_PATH=/Satori/Neuron/config/ipfs

WORKDIR /Satori/Neuron/satorineuron/web

#ENTRYPOINT [ "python" ]
#CMD ["python", "./app.py" ]
# this should be default
CMD ["bash", "./start_from_image.sh"]

# BUILD PROCESS:
# copy to and run from ../ (cd ..)
# \Satori> docker build --no-cache -f "Neuron/Dockerfile code" -t satorinet/satorineuron:latest .; docker push satorinet/satorineuron:latest
# OR
# \Satori> docker buildx create --use
# \Satori> docker buildx build --no-cache  -f "Neuron/Dockerfile code" --platform linux/amd64,linux/arm64 -t satorinet/satorineuron:latest --push .

# description: Miner environment and software for the Satori Network

# RUN OPTIONS
# python -m satorisynapse.run async
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --env ENV=prod satorinet/satorineuron:latest ./start.sh
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 24601:24601 -v C:\Users\jorda\AppData\Roaming\Satori\Neuron:/Satori/Neuron -v C:\Users\jorda\AppData\Roaming\Satori\Synapse:/Satori/Synapse -v C:\Users\jorda\AppData\Roaming\Satori\Lib:/Satori/Lib -v C:\Users\jorda\AppData\Roaming\Satori\Wallet:/Satori/Wallet -v C:\Users\jorda\AppData\Roaming\Satori\Engine:/Satori/Engine --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron satorinet/satorineuron:latest bash
# docker exec -it satorineuron bash



# \Satori> docker buildx build --no-cache -f "Neuron/Dockerfile" --platform linux/amd64,linux/arm64 -t satorinet/satorineuron:test --push .
# \Satori> docker pull satorinet/satorineuron:test
# \Satori> docker tag satorinet/satorineuron:test satorinet/satorineuron:latest
# \Satori> docker push satorinet/satorineuron:latest
