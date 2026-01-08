.PHONY: help setup clean install-service install-launchd uninstall-service uninstall-launchd \
        docker-build docker-run docker-stop docker-shell docker-logs

DOCKER_IMAGE := sleepless-claude
DOCKER_CONTAINER := claude-cc
CLAUDE_AUTH_DIR := $(HOME)/.claude-sleepless-agent

help:
	@echo "Sleepless Agent - Commands"
	@echo ""
	@echo "  setup              Install with uv"
	@echo "  clean              Clean cache files"
	@echo "  install-service    Install as systemd service (Linux)"
	@echo "  install-launchd    Install as launchd service (macOS)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build       Build Docker image (Rust + Claude Code)"
	@echo "  docker-run         Start Docker container"
	@echo "  docker-stop        Stop Docker container"
	@echo "  docker-shell       Open shell in container"
	@echo "  docker-logs        View container logs"
	@echo ""
	@echo "CLI usage: sle [start|stop|status|prompt]"

setup:
	uv sync
	cp -n .env.example .env 2>/dev/null || true
	@echo "✓ Setup complete"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	@echo "✓ Cache cleaned"

install-service:
	@echo "Installing systemd service..."
	sudo cp src/sleepless_agent/deployment/sleepless-agent.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable sleepless-agent
	@echo "✓ Service installed. Start with: sudo systemctl start sleepless-agent"

install-launchd:
	@echo "Installing launchd service..."
	@echo "Note: Update WorkingDirectory in plist first!"
	cp src/sleepless_agent/deployment/com.sleepless-agent.plist ~/Library/LaunchAgents/
	launchctl load ~/Library/LaunchAgents/com.sleepless-agent.plist
	@echo "✓ Service installed and running"

uninstall-service:
	sudo systemctl stop sleepless-agent
	sudo systemctl disable sleepless-agent
	sudo rm /etc/systemd/system/sleepless-agent.service
	sudo systemctl daemon-reload
	@echo "✓ Service uninstalled"

uninstall-launchd:
	launchctl unload ~/Library/LaunchAgents/com.sleepless-agent.plist
	rm ~/Library/LaunchAgents/com.sleepless-agent.plist
	@echo "✓ Service uninstalled"

# Docker targets
docker-build:
	docker build -t $(DOCKER_IMAGE) .
	@echo "✓ Docker image built: $(DOCKER_IMAGE)"

docker-run:
	@mkdir -p $(CLAUDE_AUTH_DIR)
	@mkdir -p workspace
	docker run -d \
		--name $(DOCKER_CONTAINER) \
		-v $(PWD)/workspace:/workspace \
		-v $(CLAUDE_AUTH_DIR):/home/claude/.claude \
		$(DOCKER_IMAGE)
	@echo "✅ Container started: $(DOCKER_CONTAINER)"
	@echo "  Workspace: $(PWD)/workspace -> /workspace"
	@echo "  Claude auth: $(CLAUDE_AUTH_DIR) -> /home/claude/.claude"

docker-stop:
	docker stop $(DOCKER_CONTAINER) 2>/dev/null || true
	docker rm $(DOCKER_CONTAINER) 2>/dev/null || true
	@echo "✅ Container stopped"

docker-shell:
	docker exec -it $(DOCKER_CONTAINER) bash

docker-logs:
	docker logs -f $(DOCKER_CONTAINER)
