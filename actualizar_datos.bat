@echo off
cd /d "%~dp0"
echo Actualizando datos MRP desde JDE...
python actualizar_mrp.py >> logs_actualizacion.txt 2>&1
echo Listo. Ver logs_actualizacion.txt para detalles.
