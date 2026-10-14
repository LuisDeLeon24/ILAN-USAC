FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SENTINEL_ROOT=/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY worker /src/worker
COPY theme /src/theme
COPY scripts /src/scripts
COPY api /src/api
COPY web /src/web
COPY docs /src/docs

# CPU wheels first so ultralytics does not download the default PyTorch build.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    "torch==2.14.1+cpu" "torchvision==0.29.1+cpu"

# Ultralytics next. It depends on opencv-python, which is removed below.
RUN pip install --no-cache-dir "ultralytics==8.4.171"

# Editable install without a second OpenCV distribution. Test and HTTP deps
# are not declared by ultralytics.
RUN pip install --no-cache-dir --no-deps -e "/src/worker" \
    && pip install --no-cache-dir "httpx>=0.27" "pytest>=8.3"

# Put the CPU wheels back if the ultralytics install replaced them.
RUN pip install --no-cache-dir --force-reinstall --index-url https://download.pytorch.org/whl/cpu \
    "torch==2.14.1+cpu" "torchvision==0.29.1+cpu"

# Last dependency step. Uninstalling opencv-python deletes the shared cv2 files
# while another OpenCV distribution can stay marked as installed, and pip then
# treats a later headless install as already satisfied. Remove every distribution
# and any leftover files, then install one pin compatible with ultralytics
# (opencv-python!=4.13.0.90,>=4.7.0).
RUN (pip uninstall -y opencv-python || true) \
    && (pip uninstall -y opencv-contrib-python || true) \
    && (pip uninstall -y opencv-python-headless || true) \
    && python -c "import shutil, site; from pathlib import Path; roots=[Path(p) for p in site.getsitepackages()]; [shutil.rmtree(child) if child.is_dir() else child.unlink() for root in roots if root.is_dir() for child in list(root.iterdir()) if child.name == 'cv2' or child.name.startswith('cv2.') or child.name.startswith('opencv_python') or child.name.startswith('opencv_contrib')]" \
    && pip install --no-cache-dir --force-reinstall "opencv-python-headless==4.12.0.88"

RUN python -c "import cv2, torch, ultralytics; print(cv2.__version__)" \
    && python -c "import importlib.metadata as m; names={d.metadata['Name'].lower() for d in m.distributions()}; assert 'opencv-python' not in names; assert 'opencv-contrib-python' not in names; assert 'opencv-python-headless' in names; import torch; assert torch.__version__.endswith('+cpu'), torch.__version__"
RUN python /src/scripts/generate_theme.py --root /src \
    && python /src/scripts/check_theme.py --root /src

WORKDIR /src/worker
CMD ["python", "-m", "app.main"]
