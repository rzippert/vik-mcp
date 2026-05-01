# Simple Makefile for Vikunja MCP

# Load .env into Make variables (if it exists)
-include .env
export

# Run the MCP server locally
run:
	uv run python -m server

# Run the test suite
test:
	uv run pytest tests

# Build a Docker image for the server
build:
	docker build -t vikunja-mcp .

# Reinitialize test environment: destroy, recreate, register user, save token
reset-test:
	@echo "==> Stopping test containers and removing volumes..."
	@docker compose -f test-instance/docker-compose.yml down -v 2>/dev/null || true
	@echo "==> Removing persisted data..."
	@rm -rf test-instance/db/* test-instance/files/*
	@echo "==> Starting fresh test containers..."
	@docker compose -f test-instance/docker-compose.yml up -d
	@echo "==> Waiting for Vikunja to become ready..."
	@until curl -s http://localhost:3456/api/v1/info >/dev/null 2>&1; do sleep 1; done
	@echo "==> Registering test user..."
	@curl -sf -X POST http://localhost:3456/api/v1/register \
		-H "Content-Type: application/json" \
		-d '{"username":"testuser","password":"testpassword123","email":"test@test.local"}' >/dev/null
	@echo "==> Logging in and saving API token..."
	@TOKEN=$$(curl -sf -X POST http://localhost:3456/api/v1/login \
		-H "Content-Type: application/json" \
		-d '{"username":"testuser","password":"testpassword123"}' | jq -r '.token'); \
	if [ -z "$$TOKEN" ] || [ "$$TOKEN" = "null" ]; then echo "ERROR: Failed to obtain token"; exit 1; fi; \
	sed -i "s|^VIKUNJA_API_TOKEN=.*|VIKUNJA_API_TOKEN=$$TOKEN|" .env; \
	sed -i "s|^os.environ\[\"VIKUNJA_API_TOKEN\"\].*|os.environ[\"VIKUNJA_API_TOKEN\"] = \"$$TOKEN\"|" tests/conftest.py; \
	echo "==> Done. Token saved to .env and tests/conftest.py"
