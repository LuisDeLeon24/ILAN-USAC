# SentinelAI - Progress

## Current phase
Phase 6 is implemented. The assistant is Senti. The dashboard uses subtle springs for new events, high and critical toasts, and the Métricas figures. Live analysis sits inside Cámaras: the page is a grid, and opening a camera shows a full-width 16:9 player that fits in the viewport, with that camera's latest events in a row underneath. An admin starts and stops analysis on that page; leaving the page does not stop it. `/en-vivo` redirects to `/camaras`. The worker still serves MJPEG on the site LAN, and the API only issues a 5-minute token. WhatsApp stays limited because a Twilio trial cannot create Content Templates. Telegram remains the demo alert channel. `/` is a public pitch landing (no auth, no API data). Login stays at `/login`. A logged-in visitor who opens `/` still sees the landing; the CTA goes to Sitios when a session exists, and to `/login` otherwise.

## Completed
- Phase 1: repository layout, Docker Compose, PostgreSQL schema, JWT auth, site/camera/zone CRUD, and the single theme file from `docs/DESIGN.md`.
- Phase 2: edge vision worker, sample-video analysis, rule engine, events with snapshots, and analyzed-minutes metering. The worker uses the HTTPS device API. Video stays on the machine that runs the worker.
- Phase 3: event filters and status changes, the mouse zone editor with exclusion areas, metrics and a configurable per-minute rate, plus lighter snapshots and per-camera detection settings.
- Phase 4: sensors through the edge webhook, a simulator, alert contacts, and WhatsApp alerts (Twilio, or the console when Twilio is not configured).
- Phase 5: conversational assistant. It lists the provider's models, calls only predefined tools, and asks for confirmation before changing an event.
- Phase 6: demo seed, sidebar and panel fixes, plain-text assistant replies, Spanish `README.md`, and the five-minute script in `docs/DEMO.md`.

## Key decisions
- 2026-10-01: Local JWT (Argon2, 12-hour access token). No public signup. The first organization and admin are created from `BOOTSTRAP_*` env vars when the database has no users.
- 2026-10-01: One user belongs to one organization. Roles are `admin` (CRUD) and `operator` (read-only). Every data query filters on the organization in the token.
- 2026-10-01: Sites are in Phase 1 because cameras belong to a site.
- 2026-10-01: Zone editing is a form (normalized polygon JSON, schedule, rule type). The canvas polygon editor is Phase 3.
- 2026-10-01: The full RTSP URL is encrypted with Fernet. API responses return only a masked URL. The device config path is the one that returns the decrypted URL to the worker.
- 2026-10-01: Compose runs `web`, `api`, `worker`, `postgres`, `redis`, and `minio`.
- 2026-10-01: `theme/tokens.toml` is the only source of colors, sizes, and weights. `scripts/generate_theme.py` writes CSS and Python. `scripts/check_theme.py` fails the image build on any other color or raw px/font size.
- 2026-10-01: The palette is navy `#0A1A3F`, cream `#FFEBE8`, white `#FFFFFF`, and cyan `#3CC8F0`. Cyan is only for outlines, active borders, focus rings, thin lines, and the city-map lights. Panels are an opaque lighter navy (white at the surface opacity mixed into navy). Cream and white on that navy meet WCAG AA.
- 2026-10-01: Two restricted colors join that palette. `charcoal` (`#1C1F26`) is only the assistant panel. `status_online` (`#2ECC71`) is only the filled connection dot. Offline stays a hollow cream dot. The theme check allows exactly these six colors and rejects either restricted color outside its surface. Cream, white, and secondary cream on charcoal meet WCAG AA.
- 2026-10-01: API and theme scripts use Python 3.12 inside Docker. The host Python version is not used.
- 2026-10-01: Docker Hub no longer serves MinIO images. Compose builds community release `RELEASE.2025-10-15T17-29-55Z` from the archived GitHub source. The API creates the `snapshots` bucket on startup.
- 2026-10-01: Login accepts local demo addresses such as `admin@sentinel.local`. The strict email library rejects the `.local` suffix.
- 2026-10-01: In production the worker runs on an edge device at the client site. The API, web app, and databases run in the cloud. Video never leaves the site. The worker talks to the API only over HTTPS with a per-device token: register the device, send events with snapshots, report analyzed minutes, heartbeat with the model version, and receive zone and rule config. It buffers events locally when the internet drops. Docker Compose stays the local development setup.
- 2026-10-01: A zone schedule is when the rule is armed. Intrusion, loitering, and occupancy fire only inside that window. After hours fires when a person is in the zone outside the window. The zone form defaults to 00:00–23:59, every day.
- 2026-10-01: When `BOOTSTRAP_DEVICE_TOKEN` is set, the API creates one demo device for the earliest site. Compose passes the same value to the worker.
- 2026-10-01: File cameras default to loop off (`una sola vez`). RTSP still forces loop off. An explicit loop still repeats and each pass is metered as its own span. The demo seed also leaves its three file cameras disabled, so the worker does not play `demo1.mp4` until someone turns one on.
- 2026-10-01: The worker image installs CPU-only PyTorch (`torch==2.14.1+cpu`), then `ultralytics==8.4.171`, then a single pin `opencv-python-headless==4.12.0.88` as the last dependency step. Ultralytics depends on `opencv-python`, and uninstalling that package deletes the shared `cv2` files while another OpenCV distribution can stay marked installed. The image removes every OpenCV distribution and leftover `cv2` files before the pin. The build runs `python -c "import cv2, torch, ultralytics; print(cv2.__version__)"` and fails if that import fails.
- 2026-10-01: Operators stay read-only for sites, cameras, zones, exclusions, detection settings, and the rate. They can change event status. Response time is the first change from nuevo to en revisión (`reviewed_at`). A jump straight to resuelto or falso positivo does not count.
- 2026-10-01: Sampled frames are scaled to a maximum width of 1280 before detection, overlays, and JPEG encoding. Normalized zone coordinates stay 0–1.
- 2026-10-01: Each camera has a minimum confidence (default 0.35) and a minimum box area as a fraction of the frame (default 0, no size filter). Exclusion polygons drop any detection whose foot point falls inside them. They do not create events.
- 2026-10-01: A clean editor frame is on demand. An admin calls `POST /cameras/{id}/frame-request`. Device config exposes `frame_requested`. The worker uploads one clean 1280px JPEG, and the API clears the flag. The frame expires after 10 minutes. Nothing is uploaded while nobody is editing.
- 2026-10-01: Each organization has one pricing plan, currency GTQ. The rate starts at 0. Estimated cost is this month's analyzed minutes times that rate. Real billing stays out of scope.
- 2026-10-01: Sensor readings enter on the edge worker (`POST /sensors` on port 8081, bearer `SENSOR_WEBHOOK_TOKEN`), then the worker forwards them with the device token. The same local outbox holds them if the API is unreachable. A sensor panel on the site LAN does not call the cloud API directly.
- 2026-10-01: Only the alarm state creates an event. Door `open` is medium, motion `detected` is low, smoke `alarm` and panic `pressed` are critical. Closed and clear states are accepted and stored as nothing. Motion is recorded and does not send WhatsApp.
- 2026-10-01: Events still use `EVENT_COOLDOWN_SECONDS` (60). WhatsApp uses `ALERT_COOLDOWN_SECONDS` (600) per camera+zone+rule, or per sensor+event type. Panic and smoke always alert. A cooled alert writes one `alert_logs` row with status `suppressed` and detail `Enfriamiento de alertas`.
- 2026-10-01: Twilio is used only when account SID, auth token, and `TWILIO_WHATSAPP_FROM` are all set. Otherwise `ConsoleProvider` logs the Spanish text. Snapshots are attached only when `PUBLIC_BASE_URL` is set; locally the alert is text only.
- 2026-10-01: Twilio WhatsApp delivers free-form text only within 24 hours of the recipient's last message to that same sender. The Messages request is URL-encoded form data with `From`, `To`, and `Body`. A failed attempt stores the Twilio error code, the Twilio message, and those parameter names. `TWILIO_CONTENT_SID` is optional and is sent only after Twilio rejects the free-form message because the session window is closed or ContentSid is required.
- 2026-10-01: **Enviar alerta de prueba** sends through the same dispatcher and writes `alert_logs` rows marked as test. It does not create an event, so it does not appear in Eventos or change Métricas.
- 2026-10-01: A Twilio trial cannot create Content Templates. WhatsApp stays implemented and is limited to free-form text inside the 24-hour window. Telegram is the demo channel that can attach the snapshot on this machine.
- 2026-10-01: Each alert contact has a channel, `whatsapp` or `telegram`. Telegram contacts store a `chat_id` chosen from chats that sent `/start` to the bot (`getUpdates`, no offset, so the chat stays listed). Nobody types a chat id. `TelegramProvider` posts `sendMessage` for text and multipart `sendPhoto` for the snapshot bytes, so Telegram does not need `PUBLIC_BASE_URL`. The same dispatcher and the same 600-second alert cooldown apply. `alert_logs.provider` is `telegram` for that channel. The test button sends through every active contact.
- 2026-10-01: The assistant uses `LLM_PROVIDER` (`gemini`, `openai`, or `anthropic`) and `LLM_API_KEY`. Model names are not hardcoded. On first use the API calls the provider's list-models endpoint and caches a model that supports function calling. Gemini prefers a Flash model and ranks by version, skipping preview, experimental, omni, live, and media-only ids. `LLM_MODEL` overrides that choice and must be a listed function-calling model. The selected id is logged once. If it is missing, the assistant says: "El modelo configurado no está disponible. Revisa LLM_MODEL en la configuración."
- 2026-10-01: Gemini function-call parts include a `thoughtSignature`. The next request sends that signature back with the tool result. Without it, Gemini rejects the follow-up.
- 2026-10-01: Tools are `search_events`, `count_events`, `summarize_events`, `get_event`, `change_event_status`, `get_usage`, and `get_equipment_status`. Every query filters on the user's organization. The model never receives snapshots, RTSP URLs, file paths, device tokens, phones, or Telegram chat ids. Relative dates are resolved in America/Guatemala. A status change is stored as a pending action and runs only after Confirmar, or after the user replies sí, si, confirmo, or adelante. Operators can confirm a status change. Both roles can read minutes, estimated cost, and the current rate. No tool changes the rate.
- 2026-10-01: HTTP 429 becomes "El asistente está recibiendo muchas consultas. Espera un momento e inténtalo de nuevo." Other provider failures become "No se pudo consultar al asistente. Inténtalo de nuevo." Both are assistant messages, not error pages. Each provider call waits up to 90 seconds. The web rewrite waits up to 5 minutes so a tool round-trip is not cut off at the 30-second proxy default.
- 2026-10-01: On Gemini's free tier, prompts and event metadata may be used by Google to improve its products. Production with real client data must use a paid tier.
- 2026-10-01: Gemini model choice prefers a function-calling Flash-Lite id, then another Flash, then any Flash, still skipping preview, experimental, omni, live, and media-only ids. `LLM_MODEL` still overrides that choice. A 429 is retried up to three times (2 s, 4 s, 8 s, or `Retry-After` capped at 20 s) before the Spanish wait message.
- 2026-10-01: The three suggested questions are answered from the database with no model call: intrusions this week, critical events yesterday, and this month's minutes plus estimated cost. Any other question still goes through the model. The system prompt asks for one `briefing` call on those three topics and forbids Markdown. Stored assistant text has asterisks and backticks removed.
- 2026-10-01: `python -m app.seed` does nothing until `--reset`. It then prints the rows it will delete, wipes every application table, and loads one organization. Without at least six annotated JPEGs in `SEED_DIR` it exits before deleting anything. Frames come from `python -m app.demo_frames` in the worker image: 6–8 distinct frames of `data/videos/demo1.mp4`, detected and annotated, saved under `data/seed/` (gitignored).
- 2026-10-01: The demo admin is Elena Morales. The email, password, and organization name still come from `BOOTSTRAP_*`. The rate is 0.01 GTQ per minute. The alert contact is WhatsApp `+50200000000`, named Central de monitoreo, and inactive. Seeded cameras are Acceso norte, Patio de carga, and Andén bodega, all file sources, 2 FPS, disabled, and not looping.
- 2026-10-01: Live video stays on the site network. The worker publishes an MJPEG stream on port 8081 only while at least one viewer is connected, at the camera's analysis FPS, max width 1280, with the existing white overlay (boxes, Persona, zones, dashed exclusions). The API issues an HMAC token to a logged-in user of that organization; it expires in 5 minutes and is not a proxy for the bytes. `WORKER_PUBLIC_URL` is the address the browser can reach. `LIVE_STREAM_SECRET` is shared by the API and the worker.
- 2026-10-02: En vivo is not a sidebar item. `/en-vivo` redirects to `/camaras`. The cameras page is a grid: name, site, Analizando / Inactiva / Sin señal, today's event count, and a small preview. The preview opens the worker stream only while the card is on screen and the camera is enabled, and it paints about once every 2 seconds. Inactive cameras show the latest event snapshot, or an empty state. A card opens `/camaras/[id]`, the large live view with that camera's latest events. Zonas and Configuración are buttons on that page. Agregar cámara is admin-only and is the only place the create form appears.
- 2026-10-02: The public pitch lives at `/` and does not call the API. Slides snap to the viewport; arrow keys, Page Up/Down, and Space move between them, and the wheel or a finger still scrolls. Team cards come only from `web/content/team.ts` (`name`, `role`, optional `photo` file in `assets/team/`, optional `linkedin`). A missing photo shows the initials of the name. The login wordmark stays centered on the panel, with no icon tile.
- 2026-10-03: Dashboard motion uses `@react-spring/web` 10.1.2, which accepts React 19. Every spring is critically damped. `prefers-reduced-motion: reduce` sets `Globals.assign({ skipAnimation: true })` for the whole app. New events on Eventos and under a camera slide in from the top and push the cards already there. A high or critical event toasts from the bottom-right on any dashboard page, shows type, severity, camera or sensor, and time, dismisses after 6 seconds, and opens that event when clicked. At most three toasts stack. On Métricas the large numerals count up from zero and the daily bars grow from the baseline with a short stagger. Detection overlays on the video are not animated.
- 2026-10-03: The camera page player fills the content width at 16:9, and its height is capped so the player fits in the viewport. Analizando sits on the video. Latest events are a horizontal row of cards under the player. Admins get Iniciar análisis and Detener análisis beside Zonas and Configuración. Start enables the camera and, for a file source, turns loop on. Stop disables the camera. While frames are still arriving the player says Conectando… and retries the stream. Leaving the page does not disable the camera.
- 2026-10-03: The assistant is Senti. The page title is Senti, the subtitle is "Tu asistente de seguridad", and an empty thread says "Hola, soy Senti. Pregúntame qué pasó en tus sitios." The system prompt introduces itself as Senti. Its messages use the existing S icon. The composer is the only surface allowed to blur or use a gradient: a translucent navy glass bar and an elliptical aurora that rises through the bottom 45% of the bar, made from glow blue, cyan, and a hint of cream. Idle it stays at 45% strength. While Senti is thinking a spring takes it to full strength, drifts the centers, and pulses it. Reduced motion keeps the static glow. The + menu holds the suggested questions. A site pill ("Todos los sitios" or one site) is applied inside the tools, not only in the prompt. The microphone uses the browser speech API (es-GT, then es-ES) and stays hidden when that API is missing. × clears the draft; a long press or "Nueva conversación" clears the thread.
- 2026-10-03: The demo rate is 0.005 GTQ per minute. Puerta norte (`puerta-norte`) and Detector de humo (`humo-planta`) are on Planta norte, the site of the demo edge device, so the simulator in `docs/DEMO.md` creates events. Movimiento patio stays there too. Bodega central keeps Andén bodega. The seed does not include a Humo patio sensor.

## How to run
From the repository root, with Docker Desktop running:

Build one image at a time. A parallel `docker compose build` has left the worker without a working OpenCV install.

```powershell
copy .env.example .env
docker compose build minio
docker compose build api
docker compose build worker
docker compose build web
docker compose up -d
```

- Web: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001
- Login after the seed: the email and password in `.env` (`elena.morales@sentinel.com.gt` / `admin12345` in the example). The display name is Elena Morales.

The first MinIO build compiles from source. The first worker build downloads the CPU PyTorch wheels. Later starts reuse the images.

Load the demo only when the current database can be replaced:

```powershell
docker compose run --rm worker python -m app.demo_frames
docker compose run --rm --no-deps api python -m app.seed --reset
```

Without `--reset` the seed prints how to continue and exits 2. It prints the deletion counts before it deletes. The script in `docs/DEMO.md` is the five-minute walkthrough. `README.md` is the Spanish setup guide.

## How to see detections
1. Log in and open **Eventos**. Filter by date, type, severity, and camera. Each row has a snapshot and a status: nuevo, en revisión, resuelto, or falso positivo.
2. Open a camera from **Cámaras**, then **Zonas**. **Actualizar cuadro** asks the worker for one clean frame. Draw a zone or an exclusion on it.
3. Open **Métricas** for this month: events per day, average time until en revisión, minutes analyzed, and estimated cost.
4. Worker logs show each sampled frame that contains a person or vehicle, then the event and the usage report. A requested frame logs `frame sent`:

```powershell
docker compose logs worker --tail 50
```

Look for `detection`, `event sent`, `usage sent`, and `file ended`. A seeded camera stays idle until it is enabled. Leave loop on **Una sola vez**, wait for one pass, then disable it again. Turning loop on keeps creating events.

Local check on 2026-10-01 after the OpenCV image rebuild: the worker read `/videos/demo1.mp4`, sent an `intrusion` event with a snapshot, and reported `minutes=0.17` for a loop. That flood was replaced by the Phase 6 seed.

## How to test
```powershell
docker compose run --rm --no-deps api pytest -q
docker compose run --rm --no-deps --entrypoint pytest worker -q
```

Phase 1 result: 16 passed. Covered zone validation, RTSP encryption and masking, tenant isolation, operator forbidden writes, health checks, and the theme gate.

Phase 2 result: API 21 passed, worker 23 passed. The worker suite includes a test that imports `cv2` and opens a tiny generated video.

Phase 3 result: API 26 passed, worker 27 passed. Covered event filters and status, `reviewed_at`, operator permissions, metrics cost, the on-demand frame, detection settings, exclusion polygons, the 1280 resize, and the one-upload latch.

Browser check on 2026-10-01 for Phase 3: login reaches Sitios. **Eventos** lists Acceso demo intrusions with filters and status. The newest snapshot is 1280×720; older ones stay at the source size. Changing one event to **en revisión** updated the marker and **Métricas** showed a response time (43 s), 51.68 analyzed minutes, a daily chart, and Q0.00 at the default rate. The zone editor for **Acceso demo** received a 1280×720 frame after **Actualizar cuadro**, and clicks on that frame placed polygon points. **Cámaras** shows confianza 0.35 and tamaño mínimo sin límite.

A demo site named "Planta norte" was created in the local database during the Phase 1 check. **Acceso demo** is the file camera used for Phase 2.

Phase 4 result: API 46 passed, worker 41 passed. Covered sensor tenancy, alarm versus clear states, the 60 s event cooldown, motion without an alert, the 600 s alert cooldown, critical smoke and panic always alerting, a suppressed log, text-only alerts, a signed snapshot URL, a mocked Twilio failure, a test send that does not create an event, and the exact Twilio form fields (`From`, `To`, `Body`). Telegram coverage: multipart `sendPhoto` with the snapshot bytes, `sendMessage` for text, a redacted Telegram error, contacts split by channel, `/start` chats from `getUpdates` with no offset, the same alert cooldown, and the test button sending every active channel.

Phase 5 result: API 65 passed, worker 41 passed. The API suite uses a fake provider and never calls a real model. It covers Guatemala date windows, Flash ranking, the Spanish message when the model list is empty or `LLM_MODEL` is missing, Gemini thought-signature replay, tenant isolation, confirmation before a status write, operator cost reads, and the tool audit log.

Browser check on 2026-10-01 for Phase 4: login reaches Sitios. **Sensores** and **Alertas** are in the sidebar. A door sensor **Puerta bodega** (`puerta-bodega`) was saved on Planta norte. **Alertas** lists intrusion attempts as Fallida / Consola / `No hay contactos activos` because no contact is active yet. **Enviar alerta de prueba** added a row `Consola · Prueba` with the same reason and did not add a row in **Eventos**. The type filter there includes Puerta abierta, Movimiento, Humo, and Botón de pánico. The simulator `open` created **PUERTA ABIERTA / MEDIA** for **Puerta bodega**. `closed` and a second `open` inside 60 seconds returned `created: false`.

Browser check on 2026-10-01 for Telegram: login reaches Sitios, then **Alertas**. The form has WhatsApp and Telegram. **Vincular Telegram** calls the bot and, with no `/start` yet, shows “Nadie ha enviado /start al bot…”. Saving without a chosen chat shows “Elige un chat de Telegram” and does not create a contact. Switching back to WhatsApp shows the phone field again. No contact was saved.

## How to test sensors and alerts
1. Log in as admin. Open **Sensores** and create one on the demo site. The external id is what the simulator sends. Operators can read sensors and cannot change them.
2. Open **Alertas**. Add a WhatsApp contact with name, number in E.164 (`+502…`), and leave it active. **Enviar alerta de prueba** does not create an event. With Twilio empty, **Intentos** shows Enviada / Consola and the API log prints the Spanish text with no image.
3. Put `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_WHATSAPP_FROM` in `.env` yourself, then recreate the API. Press the test button again. The phone receives text only while `PUBLIC_BASE_URL` is empty, and only within 24 hours of the last message to that sender. A Twilio trial cannot create Content Templates, so leave `TWILIO_CONTENT_SID` empty. A failed row shows the Twilio code, message, and parameter names.
4. For Telegram, put `TELEGRAM_BOT_TOKEN` in `.env` and recreate the API. In Telegram, open that bot and send `/start`. On **Alertas**, choose Telegram, press **Vincular Telegram**, and pick the chat. Do not type a chat id. **Enviar alerta de prueba** sends to every active contact, WhatsApp and Telegram. A camera event attaches the snapshot as a photo even when `PUBLIC_BASE_URL` is empty. **Intentos** shows Telegram. Panic and smoke still alert every time; other repeats inside 10 minutes are Suprimida.
5. From the repo root, after the worker has been up long enough to refresh config (a few seconds):

```powershell
docker compose exec worker python -m app.simulate_sensor --external-id puerta-bodega --state open
docker compose exec worker python -m app.simulate_sensor --external-id puerta-bodega --state closed
```

`open` creates **Puerta abierta**. `closed` does not. A second `open` within 60 seconds does not create another event. A later one inside 10 minutes creates the event and a Suprimida row instead of a second alert. Smoke and panic send every time.

The webhook listens on port 8081 inside the worker. Host Python is not used.

## How to test the assistant
Put `LLM_API_KEY` in `.env` and leave `LLM_MODEL` empty unless a specific model is required. Recreate the API so it reads the key. On Gemini's free tier, prompts and event metadata may be used by Google to improve its products. Production with real client data must use a paid tier.

1. Log in and open **Senti**. The thread is on top. The glass composer stays at the bottom of the panel. The + menu holds the three example questions. The site pill defaults to Todos los sitios.
2. Open + and choose "¿Cuántas intrusiones hubo esta semana?" The answer is a count for the current Monday-to-today window in Guatemala, read from the database. With a site selected, that count and the other tools stay inside that site.
3. Click "Resume los eventos críticos de ayer" or "¿Cuántos minutos se analizaron este mes y cuál es el costo estimado?" Those two also skip the model.
4. Ask a free-form question, such as "¿Cuál fue el evento más grave de ayer y qué cámaras están habilitadas?" That one calls Gemini. `docs/DEMO.md` uses it so the audience sees the model reason.
5. Ask "Marca la intrusión de Acceso norte del 1 de octubre a las 10:40 como resuelto." The event stays unchanged until **Confirmar**. **Cancelar** drops the pending change. A later look at **Eventos** shows the new status only after confirmation. The latest Acceso norte intrusion in the seed is already falso positivo, so that one does not demonstrate a change.

The API log prints `llm model selected` once, then one `agent tool` line per call. A free-tier 429 shows the Spanish wait message inside the thread.

Browser check on 2026-10-03: login reaches **Senti**. The empty thread says "Hola, soy Senti. Pregúntame qué pasó en tus sitios." beside the S icon. The composer is a glass bar with placeholder "Pregúntale a Senti…", the + menu (three questions and Nueva conversación), the site pill (Todos los sitios, Bodega central, Planta norte), the microphone, and ×. A one-time note says dictation may be processed by the browser provider. Idle, the bottom aurora is a faint line. While a question is in flight the button and the thread say Pensando… and the aurora is brighter and shifted. Nueva conversación clears the thread back to the greeting.

Phase 6 result: API 74 passed, worker 43 passed. New coverage: the seed refuses to run without `--reset` and refuses to wipe when fewer than six JPEGs are present, the inserted week uses distinct frames with cameras disabled and not looping, the rate is 0.01, the placeholder number is inactive, Flash-Lite ranks first, a 429 retries before failing, the three suggested questions skip the model, a free-form question still calls it, and stored replies drop emphasis markers.

Browser check on 2026-10-01 for Phase 6: login reaches **Sitios**. The footer shows Elena Morales and Administrador once each. Clicking Sitios, Cámaras, Sensores, Eventos, Métricas, Asistente, Alertas, Usuarios, and the wordmark each changes the page. The four panel ticks sit inside the frame. **Cámaras** lists Acceso norte, Patio de carga, and Andén bodega as archivo, una sola vez, and inactiva. **Sensores** lists Puerta norte, Movimiento patio, and Detector de humo. **Eventos** lists 37 rows across types, severities, and statuses; 20 rows have 1280×720 snapshots with detection boxes, and two of those frames are different moments. **Métricas** for octubre de 2026 shows 3,047.76 analyzed minutes and Q 30.48 for 1 October, and a September reference of 92,566.80 minutes and Q 925.67. **Alertas** shows Central de monitoreo, WhatsApp +50200000000, inactivo. The three suggested questions answered from the database: "Esta semana hubo 6 intrusiones.", the smoke event at Bodega central on 30/09/2026 04:12, and 12.00 minutes at 0.0100 GTQ for an estimated 0.12 GTQ. No tool call was stored for those three. The free-form question "¿Cuál fue el evento más grave de ayer y qué cámaras están habilitadas?" was answered by Gemini after `search_events` and `get_equipment_status`, in plain Spanish, and named the same smoke event plus the three disabled cameras. Asking to mark the latest Acceso norte intrusion asked for confirmation and left the row unchanged; **Cancelar** replied "No cambié el evento." A later request for the 10:40 intrusion stayed `new` until **Confirmar**, then became resuelto. That row and the motion at 19:40 (changed from the Eventos control during the check) were set back to nuevo so the seeded week matches the script. The assistant thread from this check is still in the database. Run the seed again before the live demo if that thread should start empty.

Browser check on 2026-10-01 for Phase 5, before the seed replaced that data: login reaches **Asistente**. The first live call listed models and selected `models/gemini-3.8-flash`. A free-tier 429 showed "El asistente está recibiendo muchas consultas. Espera un momento e inténtalo de nuevo." A later reply said this week had 417 intrusion events, and this month had 256.36 analyzed minutes at 0.0800 GTQ per minute, estimated cost 20.51 GTQ. Asking to mark the latest Acceso demo intrusion as a false positive showed Confirmar and Cancelar and left **Eventos** on Nuevo. After Confirmar, the 1/10/2026 7:58 p.m. Acceso demo row became Falso positivo. The 7:57, 7:59, and 8:00 p.m. rows stayed Nuevo. One overloaded-model response showed "No se pudo consultar al asistente. Inténtalo de nuevo." The seed removed that organization.

Browser check on 2026-10-02: `/` shows the pitch with no session. Arrow Down, Space, Page Down, and Page Up each move one section and the wheel settles on a section. Logged out, **Ingresar al centro de monitoreo** goes to `/login`, where the wordmark is centered on the panel with no tile. After login, `/` still shows the pitch and the same button goes to Sitios.

## Known issues / TODO
- The first MinIO image build compiles Go from source because the published container images are no longer available.
- On the first track call, Ultralytics may pip-install `lap` inside the running container. Tracking still produced events. Pin `lap` in the worker image if that runtime install should stop.
- The Phase 6 browser check left its assistant thread in the local database. `python -m app.seed --reset` replaces it with an empty thread and the same 37 events.
- **Métricas** charts the current calendar month. On 1 October the month-to-date total is one day (3,047.76 minutes) and the page also shows September as reference (92,566.80 minutes). Cost is those minutes times the demo rate, 0.005 GTQ. Each camera varies by at most 5% around its shift: Acceso norte 1,440 minutes, Patio de carga 840, Andén bodega 720. The assistant's "este mes" answer stays the calendar month. "Esta semana" still crosses into September. `docs/DEMO.md` says so.

## Next steps
- Follow `docs/DEMO.md` for the live walkthrough. Re-run the seed first if the assistant thread should be empty. The live door and smoke commands are in that script.
