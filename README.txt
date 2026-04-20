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

Versión nueva: IBEX + continuo filtrado
---------------------------------------
Cambios añadidos:
- universo mezclado de IBEX + continuo filtrado
- filtro automático anti-chicharros:
  - precio mínimo
  - liquidez media mínima 20d
  - ATR % máximo
- tabla con columnas extra de liquidez y volatilidad
- modo capital completo:
  - prioriza invertir el capital total en las mejores 1–3 candidatas netas
  - deja de centrarse solo en mini posiciones por riesgo
- contraste mejorado en tablas para modo oscuro

Uso recomendado
---------------
- Para empezar: IBEX + continuo filtrado activados
- Precio mínimo: 3 €
- Liquidez media mínima 20d: 750.000 €
- ATR % máximo: 8
- Capital completo: activado
- Máx. posiciones: 2


FIX aplicado
------------
Este paquete corrige un fallo de empaquetado anterior:
- ahora sí aparecen en la barra lateral:
  - Universo
  - Modo capital completo
  - Máx. posiciones para capital completo


FIX 2 aplicado
--------------
- "Modo capital completo" movido arriba del todo en la barra lateral
- cuando está activado, la salida principal ya no se centra en muchas ideas:
  ahora prioriza visualmente solo las 1–3 posiciones elegidas


FIX 3 aplicado
--------------
- nuevo filtro de entrada por extensión sobre SMA20
- nueva columna: "Extensión % sobre SMA20"
- nueva columna: "Zona de entrada" (Buena / Aceptable / Extendida)
- opción para bloquear automáticamente compras extendidas
- pensado para evitar perseguir precio en zonas malas de entrada


Panel visual rápido añadido
---------------------------
- lectura rápida del día:
  - DÍA FAVORABLE
  - DÍA OPERABLE
  - MEJOR ESPERAR
- usa:
  - contexto de mercado
  - número de zonas 'Buena'
  - número de candidatas con R/B por encima del umbral visual
- nueva columna: Acción rápida
  - ENTRAR
  - MIRAR
  - ESPERAR


FIX 4 aplicado
--------------
- filtro de mercado serio integrado
- semáforo de mercado más exigente
- opción nueva: bloquear compras si el mercado está débil
- si el mercado sale débil y el bloqueo está activo:
  - muestra "HOY NO OPERAR"
  - corta la operativa del día


Expansión de universos añadida
------------------------------
- selector de universo en la barra lateral:
  - España
  - S&P 500
  - Nasdaq 100
  - USA combinado
- nuevas listas USA filtradas para no meter todo el mercado de golpe
- el benchmark visual pasa a:
  - ^IBEX para España
  - SPY para USA
Recomendación:
- empezar con España o Nasdaq 100
- no mezclarlo todo al principio


Integración Finnhub de precio actual
------------------------------------
- proveedor principal de precio actual: Finnhub
- mapeo de tickers españoles:
  - ENG.MC -> BME:ENG
- si Finnhub falla, usa Yahoo fallback
- se muestran:
  - Fuente precio
  - Hora precio
Objetivo:
- que la entrada se base en precio realmente actual, no en cierre previo.


Corrección aplicada
-------------------
- arreglado el error de sintaxis de `from __future__ import annotations`
- `market_signal.py` ya debería abrir sin ese fallo en Windows
