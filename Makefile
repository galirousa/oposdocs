COMPOSE ?= docker compose

.PHONY: up down logs shell test migrate lint seed superuser fmt

up: .env
	$(COMPOSE) up --build -d
	@echo "→ http://localhost:8000"

.env:
	cp .env.example .env

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

shell:
	$(COMPOSE) exec web python manage.py shell

test:
	$(COMPOSE) exec web pytest

migrate:
	$(COMPOSE) exec web python manage.py migrate
	$(COMPOSE) exec web python manage.py sync_roles

lint:
	$(COMPOSE) exec web ruff check .
	$(COMPOSE) exec web ruff format --check .

fmt:
	$(COMPOSE) exec web ruff check --fix .
	$(COMPOSE) exec web ruff format .

seed:
	$(COMPOSE) exec web python manage.py seed_oposiciones
	$(COMPOSE) exec web python manage.py seed_documents

superuser:
	$(COMPOSE) exec web python manage.py createsuperuser
