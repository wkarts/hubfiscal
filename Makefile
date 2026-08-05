SHELL := /bin/bash

.PHONY: help env up down logs ps build restart migrate seed test lint format web-install web-build package

help:
	@echo "Hub Fiscal"
	@echo "  make env        Gera .env seguro"
	@echo "  make up         Sobe a stack Docker"
	@echo "  make down       Para a stack"
	@echo "  make logs       Exibe logs"
	@echo "  make migrate    Executa migrations"
	@echo "  make seed       Registra plugins padrão"
	@echo "  make test       Executa testes"
	@echo "  make package    Gera pacote ZIP"

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

package:
	./scripts/package.sh
