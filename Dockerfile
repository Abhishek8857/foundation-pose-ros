FROM osrf/ros:humble-desktop

# For Terminal bash 
SHELL ["/bin/bash", "-c"]

# Source ROS environments
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
 && echo "source /root/foundation-pose-ros/colcon_ws/install/setup.bash" >> /root/.bashrc \
 && echo "source /root/foundation-pose-ros/overlay_ws/install/setup.bash" >> /root/.bashrc

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
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,garbage_collection_threshold:0.8
ENV CUDA_HOME=/usr/local/cuda-12.4
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64
ENV PYTHONPATH=/root/foundation-pose-ros/FoundationPose:${PYTHONPATH}
ENV TORCH_CUDA_ARCH_LIST="8.6;8.9"
ENV MAX_JOBS=4
ENV FORCE_CUDA=1

# Update tools
RUN python3 -m pip install --upgrade pip setuptools wheel ninja

# Add Torch
RUN python3 -m pip install --ignore-installed sympy && \
    python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install Torch3d and Nvdiffrast
RUN python3 -m pip install --no-build-isolation "git+https://github.com/facebookresearch/pytorch3d.git" && \
    python3 -m pip install --no-build-isolation "git+https://github.com/NVlabs/nvdiffrast.git"

# Copy files
COPY /FoundationPose/ /root/foundation-pose-ros/FoundationPose/

# Change working dir
WORKDIR /root/foundation-pose-ros/FoundationPose/

# Install Requirements 
RUN python3 -m pip install -r requirements.txt && \
    python3 -m pip install --upgrade --force-reinstall --no-deps scipy matplotlib opencv-python pyparsing "warp-lang==1.8.1"

# Copy Files 
COPY /colcon_ws/src/ /root/foundation-pose-ros/colcon_ws/src/
COPY /overlay_ws/src/ /root/foundation-pose-ros/overlay_ws/src/

# Change working directory
WORKDIR /root/foundation-pose-ros/colcon_ws/
    
# Source ROS and build packages
RUN source /opt/ros/humble/setup.bash && colcon build

# Change working directory
WORKDIR /root/foundation-pose-ros/overlay_ws/
    
# Source ROS and build packages
RUN source /opt/ros/humble/setup.bash && colcon build

# Change working directory
WORKDIR /root/foundation-pose-ros/