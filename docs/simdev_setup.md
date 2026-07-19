# Isaac Task 3 runtime setup

This is the durable setup recipe for a Linux NVIDIA host or a GPU VM. The
repository is designed to run inside NVIDIA's Isaac Lab 2.3.2 container; the
host supplies Docker, the NVIDIA Container Toolkit, and an Isaac NGC login.

## Host prerequisites

```bash
docker --version
docker compose version
nvidia-smi
docker login nvcr.io
```

The Isaac Sim scene needs an RTX-capable GPU for rendering. Use the smallest
working GPU first (L4 is the baseline used by this project). Only one GPU VM
may run at a time for the shared lab account.

## Build the submission image

From a clean checkout:

```bash
docker build --tag ebim-task3:local .
```

If the NGC registry requires a specific base image, override it without
editing the repository:

```bash
docker build \
  --build-arg BASE_IMAGE=nvcr.io/nvidia/isaac-lab:2.3.2 \
  --tag ebim-task3:local .
```

## Run one autonomous episode

The container is headless by default and writes JSON/video output into the
bind-mounted `outputs/` directory:

```bash
docker run --rm --gpus all \
  -e TASK3_SEED=42 \
  -e TASK3_HEAD_PLACEMENT=a \
  -e TASK3_POLICY=scripted \
  -v "$PWD/outputs:/workspace/EBiM_Challenge/outputs" \
  ebim-task3:local
```

Use `docker run ... ebim-task3:local bash` for inspection. The default
entrypoint is intentionally explicit about `TASK3_POLICY`; a policy is not
considered submission-ready until its physical proof bundle exists.

## Run the reduced matrix

The matrix launcher is sequential so it does not oversubscribe the one-GPU
constraint:

```bash
docker run --rm --gpus all \
  -v "$PWD:/workspace/EBiM_Challenge" \
  ebim-task3:local \
  /workspace/isaaclab/isaaclab.sh -p \
  /workspace/EBiM_Challenge/scripts/task3/run_matrix.py \
  --seeds 0 1 2 3 4 --head-placements a b c
```

Before spending GPU time, inspect the exact command matrix with:

```bash
python3 scripts/task3/run_matrix.py --dry-run
```

## Export ritual

Before the lab account expires, copy `outputs/` and `proofs/` off the VM,
push the commit, and verify the proof bundle contains `result.json`,
`repro.txt`, and a playable video. A stopped VM is safe to leave as a
recoverable snapshot; an unpushed proof is not.
