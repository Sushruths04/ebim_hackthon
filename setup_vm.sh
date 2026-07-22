#!/bin/bash
set -e
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor | sudo tee /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg > /dev/null
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit git-lfs
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo docker pull nvcr.io/nvidia/isaac-lab:2.3.2
echo "DONE"
