COMPOSE ?= docker compose

.PHONY: up down logs shell test migrate lint seed superuser admin fmt harvest-day harvest-recent backfill

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

# Non-interactive admin with the development placeholder password.
admin:
	$(COMPOSE) exec web python manage.py create_admin

# --- Official source harvesting --------------------------------------------
# DAY=2026-09-01 make harvest-day
harvest-day:
	$(COMPOSE) exec web python manage.py harvest_boe --day $(DAY)

# The last N days (default 7), newest first. Same work the nightly job does.
harvest-recent:
	$(COMPOSE) exec web python manage.py harvest_boe --days $(or $(DAYS),7) --skip-done

# The full backfill, in the foreground so you can watch it. SINCE=2020-01-01.
backfill:
	$(COMPOSE) exec web python manage.py harvest_boe --backfill \
		--since $(or $(SINCE),2020-01-01) --skip-done --delay $(or $(DELAY),2)
