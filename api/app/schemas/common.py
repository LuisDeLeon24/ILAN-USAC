def normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    local, separator, domain = cleaned.partition("@")
    if not separator or not local or "." not in domain or " " in cleaned:
        raise ValueError("correo no válido")
    return cleaned


def clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("El nombre es obligatorio")
    if len(cleaned) > 200:
        raise ValueError("El nombre es demasiado largo")
    return cleaned


def normalize_polygon(value: list) -> list[list[float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("El polígono necesita al menos 3 puntos")
    cleaned: list[list[float]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Cada punto debe tener coordenadas x e y")
        try:
            x_coord, y_coord = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            raise ValueError("Cada punto debe tener coordenadas x e y") from None
        if not 0 <= x_coord <= 1 or not 0 <= y_coord <= 1:
            raise ValueError("Las coordenadas deben estar entre 0 y 1")
        cleaned.append([x_coord, y_coord])
    return cleaned


def clean_optional_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        raise ValueError("El texto es demasiado largo")
    return cleaned
