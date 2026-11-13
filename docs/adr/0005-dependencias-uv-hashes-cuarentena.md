# ADR-0005: Dependencias con uv, hashes y cuarentena de 7 días

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
OWASP A03:2025 (cadena de suministro) exige dependencias reproducibles y verificables. Varios ataques
recientes consistieron en publicar versiones maliciosas que se instalaron en sus primeras horas.

## Decisión
- **uv** gestiona el proyecto: `pyproject.toml` declara los rangos y `uv.lock` fija las versiones con
  sus hashes.
- `[tool.uv] exclude-newer = "7 days"` hace que el resolvedor ignore los artefactos publicados hace
  menos de 7 días (**cuarentena**).
- Docker y Render instalan con `pip install --require-hashes --no-deps -r requirements/*.txt`. Esos
  archivos se exportan del lock y el CI verifica que estén sincronizados.
- Las imágenes Docker se fijan por digest y las GitHub Actions por SHA de commit.
- Dependabot actualiza con un `cooldown` de 7 días. `pip-audit` y el SBOM CycloneDX corren en el CI.
- Las librerías JS se sirven localmente y se verifican contra el `integrity` (sha512) publicado en npm.

## Versiones verificadas (12-nov-2026)
- Django 5.2.19 LTS. La última versión es la 6.1.3 (ver ADR-0002).
- Paquetes publicados hace menos de 7 días: psycopg 3.3.9, boto3, gunicorn 27.0.1, django-allauth
  65.22.0, sentry-sdk, faker, ruff 0.17.5, coverage, semgrep, playwright 1.65.1 y uv 0.13.8. De estos,
  el lock toma la versión anterior.
- `django-ratelimit` 4.1.0 no tiene releases desde 2023; su compatibilidad se valida en la Fase 2.
- En el equipo de desarrollo se instaló `uv` 0.13.7, porque la 0.13.8 tenía 1 día de publicada.
- Imágenes fijadas por digest: `python:3.12-slim-trixie`, `postgres:17-alpine` y
  `valkey/valkey:8-alpine`.
- GitHub Actions fijadas por SHA: `actions/checkout` v7.0.1, `astral-sh/setup-uv` v10.3.3 y
  `actions/upload-artifact` v7.0.2. Trivy v0.76.2 se usa como imagen Docker fijada por digest, no
  como action.
- Frontend: Tailwind CSS 4.3.5 (binario standalone verificado con su `sha256sums.txt`), htmx 2.0.11 y
  @alpinejs/csp 3.17.5.

## Consecuencias
- Builds reproducibles e inmunes a versiones recién comprometidas durante su primera semana.
- Un parche de seguridad urgente se puede adoptar antes de cumplir la cuarentena con un override
  explícito, documentado en el CHANGELOG.

## Alternativas consideradas
- **pip-tools**: también genera hashes, pero es más lento y no trae la cuarentena de forma nativa.
- **Poetry**: su lock no se exporta con hashes de forma tan directa y suma otro gestor.
