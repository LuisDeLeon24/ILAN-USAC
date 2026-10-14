# Guía de instalación

Instrucciones para ejecutar Sentinel en una computadora local con Docker. Volver al [README](../README.md).

## Requisitos

- Windows 10 o 11 con [Docker Desktop](https://www.docker.com/products/docker-desktop/) en ejecución.
- Espacio en disco para la primera compilación: MinIO se construye desde el código fuente y el worker descarga PyTorch para CPU.
- Un video de muestra en `data/videos/demo1.mp4`. Dentro del worker esa ruta es `/videos/demo1.mp4`.
- PowerShell, desde la raíz del repositorio.

No hace falta Python en el host. Todo corre dentro de Docker.

## Puesta en marcha

1. Copia la plantilla de variables:

```powershell
copy .env.example .env
```

2. Construye cada imagen por separado. No uses `docker compose build` sin nombre de servicio: un build en paralelo ha fallado en esta máquina.

```powershell
docker compose build minio
docker compose build api
docker compose build worker
docker compose build web
```

La primera vez el worker tarda: instala PyTorch de CPU, ultralytics y un solo OpenCV. Las siguientes reutilizan las capas si el Dockerfile no cambia.

3. Levanta el stack, sin `--build`:

```powershell
docker compose up -d
```

4. Abre http://localhost:3000 e inicia sesión con el correo y la contraseña de `BOOTSTRAP_ADMIN_EMAIL` y `BOOTSTRAP_ADMIN_PASSWORD` en `.env`. Con la plantilla son `elena.morales@sentinel.com.gt` y `admin12345`.

- Web: http://localhost:3000
- API: http://localhost:8000
- Documentación de la API: http://localhost:8000/docs
- Consola de MinIO: http://localhost:9001

Si cambias `.env`, recrea el servicio que lee esa variable, por ejemplo `docker compose up -d --no-deps --force-recreate api`.

## Telegram, Twilio y Gemini


**Telegram** (canal que sí adjunta la foto en esta máquina):

1. Crea un bot con BotFather y copia el token en `TELEGRAM_BOT_TOKEN`.
2. Recrea la API.
3. En Telegram, abre ese bot y envía `/start`.
4. En Alertas, elige Telegram, pulsa Vincular Telegram y selecciona el chat. Nadie escribe un chat id.

**Twilio** (WhatsApp):

1. Rellena `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` y `TWILIO_WHATSAPP_FROM`.
2. Deja `TWILIO_CONTENT_SID` vacío. Una cuenta de prueba no puede crear Content Templates.
3. El texto libre solo llega si el destinatario escribió a ese remitente en las últimas 24 horas.
4. Deja `PUBLIC_BASE_URL` vacío en local: la alerta de WhatsApp sale sin imagen. Telegram no necesita esa URL.

Si Twilio no está configurado, la alerta se escribe en el log de la API y no se envía.

**Gemini:**

1. Pon la clave en `LLM_API_KEY`. `LLM_PROVIDER` queda en `gemini`.
2. Deja `LLM_MODEL` vacío. La API elige un modelo con function calling, primero Flash-Lite y después otro Flash.
3. Recrea la API.
4. En el nivel gratuito, Google puede usar los prompts y los metadatos de eventos para mejorar sus productos. Con datos reales de un cliente hace falta un plan de pago.

## Datos de demostración

Con el stack ya levantado, y `data/videos/demo1.mp4` en su sitio:

```powershell
docker compose run --rm worker python -m app.demo_frames
docker compose run --rm --no-deps api python -m app.seed --reset
```

El primer comando saca de 6 a 8 cuadros del video, corre la detección con la imagen del worker y guarda los JPG anotados en `data/seed`. El segundo borra los datos de la aplicación y carga la demostración. Sin `--reset` no borra nada e indica cómo volver a lanzarlo. Antes de borrar, imprime cuántas filas va a eliminar.

La carga deja:

- Administrador **Elena Morales** (el correo y la contraseña siguen siendo los de `.env`). Para otro nombre, cambia `DEMO_ADMIN_NAME` en `api/app/services/demo_seed.py`.
- Sitios Planta norte y Bodega central.
- Tres cámaras de archivo apagadas y sin bucle, todas sobre `/videos/demo1.mp4`. En desarrollo, al registrar una cámara de archivo usa esa ruta dentro del worker. El dispositivo demo queda en el sitio más antiguo.
- Zonas, sensores, una semana de eventos variados, y minutos de cada cámara en cada día del mes en curso: Acceso norte las 24 horas, Patio de carga de 06:00 a 20:00 y Andén bodega de 18:00 a 06:00, con una variación diaria de hasta 5%. Si hoy es 1, 2 o 3, también el mes anterior completo, para que Métricas tenga un mes de referencia.
- Tarifa de 0.005 GTQ por minuto.
- Sensores en Planta norte, el sitio del dispositivo demo: Puerta norte (`puerta-norte`), Movimiento patio (`movimiento-patio`) y Detector de humo (`humo-planta`).
- Un contacto de WhatsApp inactivo, `+50200000000`.

Las cámaras nacen apagadas para que el worker no vuelva a llenar Eventos. El recorrido de cinco minutos está en [DEMO.md](DEMO.md).

## Problemas frecuentes

**OpenCV en la imagen del worker.** ultralytics instala `opencv-python` y, al quitarlo, puede borrar los archivos de `cv2` mientras otro paquete sigue marcado como instalado. El Dockerfile desinstala todas las distribuciones de OpenCV, borra los restos y deja solo `opencv-python-headless==4.12.0.88`. El build falla si `import cv2` no funciona. No mezcles otra versión a mano dentro del contenedor.

**Builds de Docker en paralelo.** Construye minio, api, worker y web de uno en uno, como en la puesta en marcha. Si un build paralelo se cortó, repite solo el servicio que falló.

**Plantillas de Twilio.** Una cuenta de prueba no puede crear Content Templates. WhatsApp queda limitado al texto libre dentro de las 24 horas desde el último mensaje del destinatario. Para la demo, usa Telegram: adjunta la instantánea sin `PUBLIC_BASE_URL`.

**Límite de Gemini (429).** En el nivel gratuito Senti reintenta solo, con esperas de 2, 4 y 8 segundos (o `Retry-After`, como máximo 20). Si sigue limitado, el hilo muestra: "Senti está recibiendo muchas consultas. Espera un momento e inténtalo de nuevo." Las tres preguntas de ejemplo se responden desde la base y no gastan una llamada al modelo.

**El worker no ve el video.** El archivo tiene que estar en `data/videos/demo1.mp4` antes de crear la cámara o de generar los cuadros. El host no ejecuta el análisis.

**La primera imagen de MinIO tarda.** Las imágenes publicadas ya no están en Docker Hub. Compose compila la versión de la comunidad desde el código archivado. Solo pasa la primera vez.
