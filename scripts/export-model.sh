#!/bin/bash
# export-model.sh - Exporta YOLOv8n a ONNX
# Ejecutar en una máquina con espacio (NO en el miniservidor)
# El archivo resultante se sube como GitHub Release
#
# Requisitos: pip install ultralytics
# Uso: bash scripts/export-model.sh

set -euo pipefail

echo "Exportando YOLOv8n a ONNX..."

python3 -c "
from ultralytics import YOLO

model = YOLO('yolov8n.pt')
model.export(format='onnx', imgsz=640, simplify=True, opset=17)
print('Modelo exportado: yolov8n.onnx')
"

mkdir -p models
mv yolov8n.onnx models/

echo ""
echo "✅ Modelo exportado en models/yolov8n.onnx"
echo ""
echo "Ahora súbelo como GitHub Release:"
echo "  gh release create v0.1.0 models/yolov8n.onnx --title 'v0.1.0' --notes 'Modelo YOLOv8n ONNX'"
