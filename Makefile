SHELL := /bin/bash

.PHONY: help env up down logs ps build restart migrate seed test lint format web-install web-build package version-check bump-patch bump-minor bump-major release-package cloudpanel-config

help:
	@echo "Hub Fiscal"
	@echo "  make env              Gera .env seguro"
	@echo "  make up               Sobe a stack Docker"
	@echo "  make down             Para a stack"
	@echo "  make logs             Exibe logs"
	@echo "  make migrate          Executa migrations"
	@echo "  make seed             Registra plugins padrão"
	@echo "  make test             Executa testes"
	@echo "  make version-check    Valida o contrato central de versão"
	@echo "  make bump-patch       Incrementa a versão patch"
	@echo "  make bump-minor       Incrementa a versão minor"
	@echo "  make bump-major       Incrementa a versão major"
	@echo "  make release-package  Gera artefatos e checksums"
	@echo "  make cloudpanel-config Valida o Compose CloudPanel"

env:
	./scripts/generate-env.sh

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

build:
	docker compose build --pull

restart:
	docker compose restart

migrate:
	docker compose exec hubfiscal-api alembic upgrade head

seed:
	docker compose exec hubfiscal-api python -m hubfiscal.bootstrap.seed

test:
	docker compose run --rm hubfiscal-api pytest -q

lint:
	docker compose run --rm hubfiscal-api ruff check .

down-volumes:
	docker compose down -v

version-check:
	./scripts/check-version.sh

bump-patch:
	python3 scripts/set-version.py --bump patch

bump-minor:
	python3 scripts/set-version.py --bump minor

bump-major:
	python3 scripts/set-version.py --bump major

package release-package:
	./scripts/package.sh release-assets

cloudpanel-config:
	docker compose --env-file deploy/cloudpanel/.env.example -f deploy/cloudpanel/compose.yaml config --quiet
