# Task 3 submission runtime. Isaac Lab is supplied by NVIDIA's NGC registry;
# building requires an authenticated `docker login nvcr.io`.
ARG BASE_IMAGE=nvcr.io/nvidia/isaac-lab:2.3.2
FROM ${BASE_IMAGE}

ENV ACCEPT_EULA=Y \
    PRIVACY_CONSENT=Y \
    OMNI_KIT_ALLOW_ROOT=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/EBiM_Challenge
COPY . /workspace/EBiM_Challenge
COPY docker/task3_entrypoint.sh /usr/local/bin/ebim-task3
RUN chmod +x /usr/local/bin/ebim-task3

ENTRYPOINT ["/usr/local/bin/ebim-task3"]
