# Role
Act as a senior full-stack engineer with experience in computer vision and SaaS products. You will build the MVP of **SentinelAI** incrementally, in phases. Before writing code, propose the repository structure and the Phase 1 plan, and wait for my confirmation.

# Product context
SentinelAI reduces response times to security threats. It uses AI to analyze cameras and sensors the client ALREADY has installed (no infrastructure replacement), detects risk events and generates automatic alerts.
- Customers: companies, industrial plants, schools/universities and logistics centers in Guatemala (later Latin America).
- Pricing model: (1) one-time setup fee per camera/sensor and (2) **pay per analyzed time** (minutes of video processed). The system MUST accurately meter analyzed minutes per camera and per organization.
- All user-facing UI text, alerts and agent responses must be in **Spanish**. Code, variable names and commits in English. Default timezone: America/Guatemala.
- Visual design: follow `docs/DESIGN.md` strictly (three color tokens, Poppins, layout tokens, brand assets in `assets/brand/`).

# MVP scope (only this)
1. **Video ingestion**: register cameras by RTSP URL or upload a video file (demo mode). Process at 2–5 FPS to save compute.
2. **AI detection**: pretrained YOLOv8/YOLO11 (ultralytics, COCO) to detect people and vehicles. On top of detections, configurable per-camera rules:
   - Intrusion: person inside a restricted polygon zone.
   - After hours: person detected outside allowed schedule.
   - Loitering: person in a zone for more than N seconds (use tracking, e.g. ByteTrack).
   - Occupancy: more than N people in a zone.
3. **Sensors**: HTTP webhook endpoint receiving sensor events in JSON (door open, motion, smoke, panic button). Include a sensor simulator script.
4. **Event engine**: every detection or sensor reading matching a rule creates an event with severity (low/medium/high/critical), camera/sensor, timestamp, snapshot (JPG with bounding boxes) and status (new / in review / resolved / false positive). Apply a cooldown to avoid duplicate alerts for the same event.
5. **WhatsApp alerts**: when an event of medium severity or higher is created, notify the monitoring operator with event type, location, time and snapshot. Implement behind an `AlertProvider` interface with two implementations: Meta WhatsApp Cloud API (or Twilio) and a `ConsoleProvider` for development.
6. **Web dashboard**:
   - Login and organizations (basic multi-tenancy: each org only sees its own data).
   - Live view: the worker serves the annotated analysis stream on the site LAN. The cloud API does not proxy that video. Latest snapshot per camera stays in the event record.
   - Zone editor: draw polygons over a camera frame.
   - Event timeline with filters (date, type, severity, camera) and status changes.
   - Metrics: events per day, average response time (from "new" to "in review"), **minutes analyzed this month** and estimated cost based on a configurable rate.
7. **AI agent**: chat panel where users ask in natural language ("¿Cuántas intrusiones hubo esta semana en la bodega?", "Resume los eventos críticos de ayer", "Marca el evento #42 como falso positivo"). Implement with an LLM using tool calling over safe functions (query events, aggregate stats, change status). NEVER allow free-form LLM-generated SQL; the agent only uses defined tools, always scoped to the user's organization.

# Out of scope (do not build now)
Facial recognition, custom weapon/fire detection models, predictive analytics, mobile apps, real billing. Keep the architecture ready to add them later.

# Suggested stack
- Frontend: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts.
- Backend/API: FastAPI (Python), same language as the vision worker.
- Vision worker: Python + ultralytics + OpenCV, one process per camera. It talks to the API only over HTTPS (see Deployment architecture), including in local Docker Compose.
- Database: PostgreSQL (SQLAlchemy + Alembic). Snapshots in S3-compatible storage (MinIO locally). In production, snapshots are uploaded by the edge worker; video files stay on site.
- Auth: simple JWT or Supabase Auth. Edge workers use a separate per-device token, not a user JWT.
- Local development is orchestrated with `docker-compose` (api, worker, web, postgres, redis, minio). That compose file is not the production topology.
If you see a clearly simpler alternative for an MVP, propose it before switching.

# Deployment architecture
Production splits the system at the site boundary. Phase 2 and later phases are designed against this boundary.

- The vision worker runs on an edge device at the client's site. Video never leaves the site. Live video stays on the site's network: the worker serves an MJPEG stream of the frames it is analyzing on its LAN port, and the browser connects to that worker directly. The cloud API only issues a signed token to a logged-in user of that organization. The token expires in 5 minutes and the open page refreshes it. The API never receives or proxies the stream.
- The API, web app, and databases run in the cloud.
- The worker talks to the API only over HTTPS, authenticated with a per-device token. Through that API it registers the device, sends events with snapshots, reports analyzed minutes, sends a heartbeat that includes the model version, and receives zone and rule configuration.
- If the internet drops, the worker buffers events locally and sends them when connectivity returns.
- `docker-compose` remains the local development setup, with the worker, API, web, and databases on one machine. The worker still uses the same HTTPS contract in that setup, so local development does not depend on shared database or queue access to the cloud services.

# Minimum data model
organizations, users, sites, cameras, sensors, zones (polygon + schedule + rules), events, alert_contacts, alert_logs, usage_records (camera_id, analyzed minutes, date) and pricing_plans.

# Non-functional requirements
- Secrets in `.env` with a documented `.env.example` (WhatsApp and LLM API keys).
- RTSP credentials encrypted in the database.
- Configurable snapshot retention (default 30 days) and a README note on consent and video surveillance signage.
- Structured logging and reconnection handling if a camera drops (generate a "camera disconnected" event).
- Basic rule engine tests (pytest).
- A `seed` script with a demo organization, 2 cameras using sample videos, zones and simulated sensors, so a full demo runs with a single command.

# Phased plan (deliver and wait for my review after each phase)
1. Repo structure, docker-compose, database, auth and camera/zone CRUD. Includes the single theme/token file from `docs/DESIGN.md`.
2. Vision worker with sample videos, rule engine, events with snapshots and analyzed-minutes metering. Design it against the deployment boundary: edge worker, HTTPS per-device token, local event buffer, video stays on site.
3. Dashboard: events, zone editor, metrics and usage/cost.
4. Sensor webhook and simulator + WhatsApp alerts.
5. Conversational agent with tool calling.
6. Polish: demo seed, README in Spanish with setup instructions and a 5-minute demo script.

# Working style
- Clean, modular code.
- After each phase: list of files created, how to run it and how to test it, and update `docs/PROGRESS.md`.
- If something is ambiguous, ask me before assuming.
