MARKET SIGNAL APP
=================

Qué es
------
Aplicación local para Windows hecha en Python + Streamlit para analizar acciones y obtener señales heurísticas orientativas de compra / vigilancia / neutral / evitar.

NO es una máquina mágica ni asesoramiento financiero.
Está pensada como herramienta de apoyo a decisión.

Incluye
-------
- análisis individual de ticker
- escáner de watchlist
- score técnico heurístico
- fuerza relativa frente a benchmark
  - .MC -> ^IBEX
  - resto -> SPY
- top 3 del día del último escaneo
- filtros de candidatas operables y operables netas
- cálculo de costes
- aproximación de Tobin para acciones españolas (.MC)
- tamaño de posición
- beneficio neto esperado
- capital mínimo recomendado
- exportación Excel / CSV a la carpeta exports
- plantilla Excel de seguimiento de trades incluida

Archivos principales
--------------------
- app.py
- market_signal.py
- requirements.txt
- run_app.bat
- plantilla_seguimiento_trades.xlsx

Cómo abrirla en Windows
-----------------------
Opción simple:
1. instala Python 3.11 o 3.12 para Windows
2. descomprime la carpeta
3. haz doble clic en run_app.bat

El .bat:
- crea un entorno virtual .venv si no existe
- instala dependencias
- abre Streamlit en el navegador

Si no se abre solo, copia en el navegador la URL local que te mostrará la consola
(normalmente http://localhost:8501)

Uso recomendado
---------------
1. ajusta capital, riesgo y costes en la barra lateral
2. escanea tu watchlist
3. mira el TOP 3 DEL DÍA
4. aplica el filtro de operables netas
5. revisa el detalle de 1 a 3 ideas
6. lleva el seguimiento en la plantilla Excel

Notas de diseño
---------------
- el score es una heurística técnica, no una predicción exacta
- la estimación a 5 y 20 sesiones es orientativa
- el modelo está planteado para escenarios de compra (largos), no para cortos
- el objetivo se fuerza a mantenerse positivo y por encima del precio para evitar objetivos incoherentes
- el detalle del escáner se selecciona por ticker, evitando el error de tomar la columna de ranking

Dependencias
------------
Ver requirements.txt

Problemas típicos
-----------------
1. Yahoo Finance no devuelve datos de algún ticker
   - revisa el símbolo
   - prueba de nuevo al cabo de unos minutos

2. La consola dice que falta Python
   - instala Python desde python.org
   - durante la instalación marca "Add Python to PATH"

3. La app va lenta al escanear muchos tickers
   - es normal si la watchlist es grande porque descarga datos de varios símbolos

Validación sugerida
-------------------
- probar unas 50 operaciones simuladas
- medir:
  - % acierto
  - drawdown
  - profit factor
  - rentabilidad media
  - comparación contra benchmark

Descargo de responsabilidad
---------------------------
Esta app no garantiza resultados ni sustituye tu análisis.
Úsala como apoyo y contrasta siempre cualquier operación.


Modo capital completo añadido
-----------------------------
- nuevo modo opcional para priorizar invertir el capital total indicado
- reparte el capital entre las mejores 1–3 candidatas netas
- usa un reparto ponderado por calidad (Score x R/B neto)
- pensado para usuarios que no quieren mini posiciones repartidas en demasiadas ideas

Interpretación
--------------
- el escáner clásico sigue existiendo
- pero ahora la app también puede responder a la pregunta:
  "tengo X euros, ¿en qué 1–3 ideas los pondría?"
