"""Reset the database to the demo organization.

    python -m app.seed --reset

Refuses to delete anything until --reset is present, and prints the rows it
will remove before it removes them. Annotated frames must already be in SEED_DIR.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.services.agent.dates import GUATEMALA
from app.db.session import SessionLocal
from app.services.demo_seed import (
    DEMO_ADMIN_NAME,
    DEMO_PHONE,
    DEMO_RATE,
    MIN_FRAMES,
    deletion_lines,
    insert_demo,
    minutes_on,
    usage_dates,
    wipe_all,
)


def load_frames(directory: Path) -> list[bytes]:
    frames: list[bytes] = []
    for path in sorted(directory.glob("frame-*.jpg")):
        payload = path.read_bytes()
        if payload[:2] == b"\xff\xd8":
            frames.append(payload)
    return frames[:8]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the SentinelAI demo organization")
    parser.add_argument("--reset", action="store_true", help="Delete current data and load the demo")
    args = parser.parse_args(argv)
    if not args.reset:
        print("Este comando borra los datos de la base y carga la demostración.")
        print("Vuelve a ejecutarlo con --reset para continuar.")
        return 2
    directory = Path(os.environ.get("SEED_DIR", "/seed"))
    frames = load_frames(directory)
    if len(frames) < MIN_FRAMES:
        print(f"Faltan cuadros anotados en {directory} (hay {len(frames)}, se necesitan al menos {MIN_FRAMES}).")
        print("Genéralos con el worker antes de borrar nada:")
        print("docker compose run --rm worker python -m app.demo_frames")
        return 1
    print(f"Cuadros anotados: {len(frames)}")
    db = SessionLocal()
    try:
        lines = deletion_lines(db)
        if lines:
            print("Se borrará:")
            for line in lines:
                print(f"- {line}")
        else:
            print("No hay datos que borrar.")
        print("Esta acción no se puede deshacer.")
        wipe_all(db)
        result = insert_demo(
            db,
            frames,
            email=settings.bootstrap_admin_email,
            password=settings.bootstrap_admin_password,
            organization_name=settings.bootstrap_org_name,
            full_name=DEMO_ADMIN_NAME,
            device_token=settings.bootstrap_device_token or None,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print("Demostración lista.")
    print(f"Organización: {result.organization_name}")
    print(f"Administrador: {result.full_name} ({result.email})")
    print("Sitios: Planta norte, Bodega central")
    print("Cámaras de archivo apagadas, sin bucle: Acceso norte, Patio de carga, Andén bodega")
    print(f"Eventos: {result.events}. Instantáneas: {result.snapshots}.")
    print(f"Contacto inactivo: WhatsApp {DEMO_PHONE}")
    print(f"Tarifa: {DEMO_RATE} GTQ por minuto.")
    print("Sensores en Planta norte: puerta-norte, movimiento-patio, humo-planta")
    today = datetime.now(GUATEMALA).date()
    dated = usage_dates(datetime.now(GUATEMALA))
    current_days = [day for day in dated if day.year == today.year and day.month == today.month]
    previous_days = [day for day in dated if day < today.replace(day=1)]
    current_minutes = minutes_on(current_days)
    day_label = "día" if len(current_days) == 1 else "días"
    print(
        f"Minutos de este mes: {current_minutes} ({current_minutes * DEMO_RATE:.2f} GTQ) "
        f"en {len(current_days)} {day_label}."
    )
    if previous_days:
        previous_minutes = minutes_on(previous_days)
        print(f"Mes anterior de referencia: {previous_minutes} minutos ({previous_minutes * DEMO_RATE:.2f} GTQ).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
