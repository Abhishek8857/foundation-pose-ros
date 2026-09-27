FROM osrf/ros:humble-desktop

# Foundation Pose dependancies
RUN apt-get update && apt-get install -y \
    build-essential cmake git wget ninja-build \
    libeigen3-dev python3-pip \
    libgl1-mesa-dev libegl1-mesa-dev freeglut3-dev \
    && rm -rf /var/lib/apt/lists/*
    
# Add Cuda
RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb \
    && rm cuda-keyring_1.1-1_all.deb \
    && apt-get update \
    && apt-get install -y cuda-toolkit-12-4 \
    && rm -rf /var/lib/apt/lists/*

# Set Environment variables 
ENV CUDA_HOME=/usr/local/cuda-12.4
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}
ENV TORCH_CUDA_ARCH_LIST="8.6;8.9"

RUN python3 -m pip install --upgrade pip setuptools wheel ninja

# Add Torch
RUN python3 -m pip install --ignore-installed sympy && \
    python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

RUN python3 -m pip install --no-build-isolation "git+https://github.com/facebookresearch/pytorch3d.git" && \
    python3 -m pip install --no-build-isolation "git+https://github.com/NVlabs/nvdiffrast.git"

COPY FoundationPose/requirements.txt /tmp/
RUN python3 -m pip install -r /tmp/requirements.txt && \
    python3 -m pip install --upgrade --force-reinstall --no-deps scipy matplotlib opencv-python pyparsing
