"""Redacción de credenciales antes de imprimir o persistir configuración."""
import json
import re


SENSITIVE_NAME = re.compile(
    r"api[_-]?key|token|secret|password|authorization|credential|cookie", re.I)


def redact_value(value):
    """Copia estructuras JSON sustituyendo valores de campos sensibles."""
    if isinstance(value, dict):
        return {k: "<redacted>" if SENSITIVE_NAME.search(str(k)) else redact_value(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    return value


def redact_options(options):
    """Redacta opciones planas y también JSON anidado pasado como texto."""
    safe = {}
    for key, value in options.items():
        if SENSITIVE_NAME.search(str(key)):
            safe[key] = "<redacted>"
            continue
        if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                pass
            else:
                redacted = redact_value(parsed)
                value = (json.dumps(redacted, ensure_ascii=False, separators=(",", ":"))
                         if redacted != parsed else value)
        safe[key] = redact_value(value)
    return safe
