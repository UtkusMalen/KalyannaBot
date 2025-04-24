PYTHON = python

.SUFFIXES:

.PHONY: all help env build up start down stop logs clean restart

.DEFAULT_GOAL:=help

help:
	@echo "Available Makefile commands for KalyannaBot:"
	@echo "  make help          - Show this help message"
	@echo "  make env           - Generate/update .env file"
	@echo "  make build         - Build Docker images"
	@echo "  make up            - Start services in detached mode"
	@echo "  make start         - Same as make up'"
	@echo "  make down          - Stop and remove containers"
	@echo "  make stop          - Same as make down"
	@echo "  make restart       - Restart services"
	@echo "  make logs          - Show bot logs (press Ctrl+C to exit)"
	@echo "  make logs-db       - Show database logs"
	@echo "  make logs-all      - Show logs for all services"
	@echo "  make clean         - Stop containers and remove volumes (WARNING: DB data will be lost!)"

env:
	@echo "Generating/updating .env file..."
	@$(PYTHON) generate_env.py

build: env
	@echo "Building Docker images..."
	@docker compose build

up: build
	@echo "Starting services in detached mode..."
	@docker compose up -d

start: up

down:
	@echo "Stopping and removing containers..."
	@docker compose down

stop: down

restart: down up

logs:
	@echo "Showing bot logs (press Ctrl+C to exit)..."
	@docker compose logs -f bot

logs-db:
	@echo "Showing database logs (press Ctrl+C to exit)..."
	@docker compose logs -f db

logs-all:
	@echo "Showing logs for all services (press Ctrl+C to exit)..."
	@docker compose logs -f

clean:
	@echo "Stopping containers and removing volumes..."
	@docker compose down -v