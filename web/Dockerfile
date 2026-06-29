FROM python:3.11-slim

WORKDIR /app

# OpenMP is required by PyTorch CPU; everything else Pillow needs is bundled in its wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU torch/torchvision first — large & slow, lives in its own cached layer
# so rebuilds triggered by app-code changes don't re-download ~800 MB
RUN pip install --no-cache-dir \
        torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# Install remaining application deps (torch is already satisfied, will be skipped)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake ResNet18 ImageNet weights into the image so the server starts instantly
# without any runtime download (~46 MB, cached in /root/.cache/torch/)
RUN python - <<'EOF'
from torchvision.models import resnet18, ResNet18_Weights
resnet18(weights=ResNet18_Weights.DEFAULT)
print("ResNet18 weights cached.")
EOF

COPY . .

EXPOSE 5000

CMD ["python", "main.py", "--port", "5000"]
