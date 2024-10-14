# copy to and run from ../ or C:\repos\Satori
# (updating process is the only thing that requires git)
# (vim for troubleshooting)

# python:slim will eventually fail, if we need to revert try this:
# FROM python:slim3.12.0b1-slim
<<<<<<< HEAD
# Use the official Python image as the base image
=======
>>>>>>> main
FROM python:3.10-slim AS builder

# System dependencies
# RUN apt-get update && \
#     apt-get install -y build-essential wget curl git vim cmake dos2unix \
#     wireguard iptables iproute2 netcat-openbsd iputils-ping && \
#     apt-get clean
RUN apt-get update 
RUN apt-get install -y build-essential
RUN apt-get install -y wget curl git vim cmake dos2unix
RUN apt-get install -y wireguard iptables iproute2 netcat-openbsd iputils-ping
RUN apt-get clean 
# --fix-missing
# && rm -rf /var/lib/apt/lists/*

# File system setup
ARG BRANCH_FLAG=main
RUN mkdir /Satori && \
    cd /Satori && git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Synapse.git && \
    cd /Satori && git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Lib.git && \
    cd /Satori && git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Wallet.git && \
    cd /Satori && git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Engine.git && \
    cd /Satori && git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Neuron.git && \
    cd /Satori && git clone https://github.com/amazon-science/chronos-forecasting.git && \
    cd /Satori && git clone https://github.com/ibm-granite/granite-tsfm.git && \
    mkdir /Satori/Neuron/models && \
    mkdir /Satori/Neuron/models/huggingface && \
    chmod +x /Satori/Neuron/satorineuron/web/start.sh && \
    chmod +x /Satori/Neuron/satorineuron/web/start_from_image.sh && \
    dos2unix /Satori/Neuron/satorineuron/web/start.sh && dos2unix /Satori/Neuron/satorineuron/web/start_from_image.sh

# Install Python packages
ENV HF_HOME=/Satori/Neuron/models/huggingface
ARG GPU_FLAG=off
ENV GPU_FLAG=${GPU_FLAG}
RUN pip install --upgrade pip && \
    if [ "${GPU_FLAG}" = "on" ]; then \
    pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cu124; \
    else \
    pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu; \
    fi && \
    pip install --no-cache-dir transformers==4.44.2 && \
    pip install --no-cache-dir /Satori/granite-tsfm && \
    pip install --no-cache-dir /Satori/chronos-forecasting && \
    cd /Satori/Wallet && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Synapse && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Lib && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Engine && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Neuron && pip install --no-cache-dir -r requirements.txt && python setup.py develop

# WireGuard setup
# WireGuard setup
RUN mkdir -p /etc/wireguard
# Note: You need to provide a wg0.conf file in your build context
COPY Neuron/config/wg0.conf /etc/wireguard/wg0.conf
RUN chmod 600 /etc/wireguard/wg0.conf
## no need for ollama at this time.
#RUN apt-get install -y curl
#RUN mkdir /Satori/Neuron/chat
#RUN cd /Satori/Neuron/chat && curl -fsSL https://ollama.com/install.sh | sh
#RUN ollama serve
#RUN ollama pull llama3

# Expose ports
EXPOSE 24601
EXPOSE 51820/udp

# Copy peer_management_script.py into the container
# COPY Neuron/peer_management_script.py /app/peer_management_script.py


# Ensure the script has execute permissions
# RUN chmod +x /app/peer_management_script.py

# Set working directory
WORKDIR /Satori/Neuron/satorineuron/web

# Set the entry point
CMD ["bash", "./start_from_image.sh"]
WORKDIR /Satori/Neuron/satorineuron/web
# CMD ["bash", "./start_from_image.sh"]

## RUN OPTIONS
# python -m satorisynapse.run async
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --env PREDICTOR=ttm --env ENV=prod satorinet/satorineuron:latest ./start.sh
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --env PREDICTOR=ttm --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 24601:24601 -v C:\Users\jorda\AppData\Roaming\Satori\Neuron:/Satori/Neuron -v C:\Users\jorda\AppData\Roaming\Satori\Synapse:/Satori/Synapse -v C:\Users\jorda\AppData\Roaming\Satori\Lib:/Satori/Lib -v C:\Users\jorda\AppData\Roaming\Satori\Wallet:/Satori/Wallet -v C:\Users\jorda\AppData\Roaming\Satori\Engine:/Satori/Engine --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron satorinet/satorineuron:latest bash
# docker exec -it satorineuron bash

## BUILD PROCESS
# \Neuron> docker buildx prune --all
# \Neuron> docker builder prune --all
# \Neuron> docker buildx create --use
## dev version:
# \Neuron> docker buildx build --no-cache -f Dockerfile --platform linux/amd64             --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=dev  -t satorinet/satorineuron:test         --push .
## build both together (seems to fail some times):
# \Neuron> docker buildx build --no-cache -f Dockerfile --platform linux/amd64,linux/arm64 --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:test         --push .
## build separately:
# \Neuron> docker buildx build --no-cache -f Dockerfile --platform linux/amd64             --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:test         --push .
# \Neuron> docker buildx build --no-cache -f Dockerfile --platform linux/arm64             --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:rpi_satori   --push .
## build GPU version:
# \Neuron> docker buildx build --no-cache -f Dockerfile --platform linux/amd64             --build-arg GPU_FLAG=on  --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:test-gpu     --push .
# \Neuron> docker pull satorinet/satorineuron:test
# \Neuron> docker run --rm -it --name satorineuron -p 24601:24601 --env ENV=prod                         satorinet/satorineuron:test bash
# \Neuron> docker run --rm -it --name satorineuron -p 24601:24601 --env ENV=prod --env PREDICTOR=xgboost satorinet/satorineuron:test bash
# \Neuron> docker tag satorinet/satorineuron:test satorinet/satorineuron:latest
# \Neuron> docker push satorinet/satorineuron:latest


## RUN CPU AND GPU EXAMPLES:
# docker run --rm -it --name satorineuron -p 24601:24601 satorinet/satorineuron:latest-wil bash # create temporarily (removes container after 'exit' command)
# # create a new container instance and start it (-t includes logging, otherwise not)
# PREDICTOR options: [xgboost, ttm, chronos] (default to xgboost)
# docker run -t --name satorineuron -p 24601:24601                             --env ENV=prod --env PREDICTOR=ttm     satorinet/satorineuron:latest-wil     python ./app.py
# docker run -t --name satorineuron -p 24601:24601 --runtime=nvidia --gpus all --env ENV=prod --env PREDICTOR=chronos satorinet/satorineuron:latest-wil-gpu python ./app.py

## start an existing container
# docker start satorineuron && docker exec -it satorineuron bash
# docker start satorineuron && docker exec -t satorineuron python ./app.py
# # docker stop satorineuron

# test web
# docker run --rm -it --name satorineuron -p 5000:5000 -v c:\repos\Satori\satori:/Satori/satori --env ENV=prod --env WALLETONLYMODE=1 satorinet/satorineuron:latest python /Satori/satori/app.py

<<<<<<< HEAD
# wireguard
# docker run --rm -it --name satorineuron -p 24601:24601 -p 51820:51820/udp -v c:\repos\satori\Neuron\config:/config -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --cap-add=NET_ADMIN --cap-add=SYS_MODULE --sysctl="net.ipv4.conf.all.src_valid_mark=1" --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 24601:24601 -p 51820:51820/udp -v c:\repos\satori\Neuron\config:/config -v c:\repos\Satori\Neuron:/Satori/Neuron --cap-add=NET_ADMIN --cap-add=SYS_MODULE --sysctl="net.ipv4.conf.all.src_valid_mark=1" --network=wireguard-net --env ENV=prod satorinet/satorineuron:latest bash
# docker build --no-cache -f "Neuron/Dockerfile" -t satorinet/satorineuron:latest .
# docker build --no-cache -f Dockerfile -t satorinet/satorineuron:latest .
# docker exec -it satorineuron bash
#  docker build --progress=plain -t satorinet/satorineuron:latest .
=======
# automatic fast slow build:
# docker buildx build --no-cache -f Dockerfile --platform linux/amd64             --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:test         --push .
# docker pull satorinet/satorineuron:test
# docker tag satorinet/satorineuron:test satorinet/satorineuron:latest
# docker push satorinet/satorineuron:latest
# docker buildx build --no-cache -f Dockerfile --platform linux/amd64,linux/arm64 --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:test         --push .
# docker pull satorinet/satorineuron:test
# docker tag satorinet/satorineuron:test satorinet/satorineuron:latest
# docker push satorinet/satorineuron:latest
# docker buildx build --no-cache -f Dockerfile --platform linux/arm64             --build-arg GPU_FLAG=off --build-arg BRANCH_FLAG=main -t satorinet/satorineuron:rpi_satori   --push .
# echo "Done!"
>>>>>>> main
