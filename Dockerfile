# copy to and run from ../ or C:\repos\Satori
# (updating process is the only thing that requires git)
# (vim for troubleshooting)

# python:slim will eventually fail, if we need to revert try this:
# FROM python:slim3.12.0b1-slim
FROM python:3.10-slim AS gitclone

## System dependencies
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        wget \
        curl \
        git \
        vim \
        cmake \
        dos2unix \
        libleveldb-dev && \
    apt-get clean
    # TODO: need zip? I think it was just used for IPFS install
    #apt-get install -y zip

# TODO: test 777 permissions
    #chmod -R 777 /Satori/Lib && \
    #chmod -R 777 /Satori/Engine && \
    #chmod -R 777 /Satori/Neuron && \
## File system setup
ARG GITHUB_USERNAME
ARG GITHUB_TOKEN
ARG BRANCH_FLAG=main
RUN mkdir /Satori && \
    cd /Satori && \
    git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Lib.git && \
    git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Engine.git && \
    git clone -b ${BRANCH_FLAG} https://github.com/SatoriNetwork/Neuron.git && \
    rm -rf /root/.gitconfig /root/.ssh /root/.netrc && \
    mkdir -p /Satori/Neuron/models/huggingface && \
    chmod +x /Satori/Neuron/satorineuron/web/start.sh && \
    chmod +x /Satori/Neuron/satorineuron/web/start_from_image.sh && \
    dos2unix /Satori/Neuron/satorineuron/web/start.sh && \
    dos2unix /Satori/Neuron/satorineuron/web/start_from_image.sh
    # NOTE: dos2unix line is used to convert line endings from Windows to Unix format
    # for private repos: git clone -b ${BRANCH_FLAG} https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/SatoriNetwork/Engine.git && \

# Stage 2: Final image
FROM python:3.10-slim AS builder

COPY --from=gitclone /Satori /Satori

## Install everything
ENV HF_HOME=/Satori/Neuron/models/huggingface
ARG GPU_FLAG=off
ENV GPU_FLAG=${GPU_FLAG}
# for torch: cpu cu118 cu121 cu124 --index-url https://download.pytorch.org/whl/cpu
ENV PIP_DEFAULT_TIMEOUT=100

RUN apt-get update && \
    apt-get install -y \
        build-essential \
        wget \
        curl \
        git \
        vim \
        cmake \
        dos2unix \
        libleveldb-dev && \
    apt-get clean

# testing
#pip uninstall granite-tsfm; rm -rf granite-tsfm; git clone -b v2.0.6 https://github.com/ibm-granite/granite-tsfm.git; pip install --no-cache-dir /Satori/granite-tsfm
#pip uninstall granite-tsfm nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 nvidia-cufft-cu12 nvidia-cufile-cu12 nvidia-curand-cu12 nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-cusparselt-cu12 nvidia-nccl-cu12 nvidia-nvjitlink-cu12 nvidia-nvtx-cu12
# du -sh /usr/local/lib/python3.10/site-packages/* | sort -h
# rm -rf /usr/local/lib/python3.10/site-packages/nvidia

RUN cd /Satori && \
    git clone -b v1.5.2 https://github.com/amazon-science/chronos-forecasting.git && \
    git clone https://github.com/ibm-granite/granite-tsfm.git && \
    cd granite-tsfm && \
    git checkout 43f2a35d76fe9a6c7fb5714b2cbff57eaa7c3980 && \
    cd .. && \
    pip install --upgrade pip && \
    if [ "${GPU_FLAG}" = "on" ]; then \
        pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cu124; \
        pip install triton nvidia-pyindex nvidia-cublas-cu12; \
    else \
        pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu; \
    fi
RUN pip install --no-cache-dir transformers==4.51.3
RUN pip install --no-cache-dir /Satori/granite-tsfm
RUN pip install --no-cache-dir /Satori/chronos-forecasting

# erase nvidia if GPU_FLAG is off
#RUN if [ "${GPU_FLAG}" = "on" ]; then \
#        echo "GPU_FLAG is on"; \
#    else \
#        rm -rf /usr/local/lib/python3.10/site-packages/nvidia; \ 
#    fi

RUN cd /Satori/Lib && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Engine && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    cd /Satori/Neuron && pip install --no-cache-dir -r requirements.txt && python setup.py develop && \
    rm -rf /root/.cache /root/.local

## no need for ollama at this time.
#RUN apt-get install -y curl
#RUN mkdir /Satori/Neuron/chat
#RUN cd /Satori/Neuron/chat && curl -fsSL https://ollama.com/install.sh | sh
#RUN ollama serve
#RUN ollama pull llama3

# satori ui
EXPOSE 24601

WORKDIR /Satori/Neuron/satorineuron/web
CMD ["bash", "./start_from_image.sh"]

## RUN OPTIONS
# docker run --rm -it --name satorineuron -p 24601:24601 -v ~/repos/Satori/Neuron:/Satori/Neuron -v ~/repos/Satori/Lib:/Satori/Lib -v ~/repos/Satori/Engine:/Satori/Engine --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Engine:/Satori/Engine --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron -v c:\repos\Satori\Synapse:/Satori/Synapse -v c:\repos\Satori\Lib:/Satori/Lib -v c:\repos\Satori\Wallet:/Satori/Wallet -v c:\repos\Satori\Engine:/Satori/Engine --env PREDICTOR=ttm --env ENV=prod satorinet/satorineuron:latest ./start.sh
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
# docker run --rm -it --name satorineuron -p 127.0.0.1:24601:24601 --env ENV=prod -v c:\repos\Satori\Neuron\wallet:/Satori/Neuron/wallet -v c:\repos\Satori\Neuron\models:/Satori/Neuron/models -v c:\repos\Satori\Neuron\data:/Satori/Neuron/data -v c:\repos\Satori\Neuron\config:/Satori/Neuron/config satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 127.0.0.1:24601:24601 --env ENV=prod satorinet/satorineuron:latest bash
# docker run --rm -it --name satorineuron -p 127.0.0.1:24601:24601 --env ENV=prod satorinet/satorineuron:test bash

#### automatic fast slow build:
# docker tag satorinet/satorineuron:latest satorinet/satorineuron:previous
# docker tag satorinet/satorineuron:latest satorinet/satorineuron:0.3.9
## fast
# export $(grep -v '^#' .env | xargs)
# docker buildx build --no-cache -f Dockerfile --platform linux/amd64 --build-arg GPU_FLAG=$GPU_FLAG --build-arg BRANCH_FLAG=$BRANCH_FLAG --build-arg GITHUB_USERNAME=$GITHUB_USERNAME --build-arg GITHUB_TOKEN=$GITHUB_TOKEN -t satorinet/satorineuron:test         --push . 
# docker pull satorinet/satorineuron:test
# docker tag satorinet/satorineuron:test satorinet/satorineuron:latest
# docker push satorinet/satorineuron:latest
# unset GITHUB_USERNAME GITHUB_TOKEN
## slow
# export $(grep -v '^#' .env | xargs)
# docker tag satorinet/satorineuron:p2p satorinet/satorineuron:p2p-previous
# docker buildx build --no-cache -f Dockerfile --platform linux/amd64,linux/arm64 --build-arg GPU_FLAG=$GPU_FLAG --build-arg BRANCH_FLAG=$BRANCH_FLAG --build-arg GITHUB_USERNAME=$GITHUB_USERNAME --build-arg GITHUB_TOKEN=$GITHUB_TOKEN -t satorinet/satorineuron:p2p         --push .
# docker pull satorinet/satorineuron:p2p
# docker tag satorinet/satorineuron:test satorinet/satorineuron:latest
# docker push satorinet/satorineuron:latest
# docker buildx build --no-cache -f Dockerfile --platform linux/arm64             --build-arg GPU_FLAG=$GPU_FLAG --build-arg BRANCH_FLAG=$BRANCH_FLAG --build-arg GITHUB_USERNAME=$GITHUB_USERNAME --build-arg GITHUB_TOKEN=$GITHUB_TOKEN -t satorinet/satorineuron:rpi_satori   --push .
# unset GITHUB_USERNAME GITHUB_TOKEN
# echo "Done!"


# p2p
# docker run --rm -it --name satorineuron --network host -v ~/repos/Satori/Neuron:/Satori/Neuron -v ~/repos/Satori/Lib:/Satori/Lib -v ~/repos/Satori/Engine:/Satori/Engine --env ENV=testprod satorinet/satorineuron:p2p bash
# docker exec -it satorineuron bash