.PHONY: help setup clean install-service install-launchd uninstall-service uninstall-launchd

help:
	@echo "Sleepless Agent - Commands"
	@echo ""
	@echo "  setup              Install with uv"
	@echo "  clean              Clean cache files"
	@echo "  install-service    Install as systemd service (Linux)"
	@echo "  install-launchd    Install as launchd service (macOS)"
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
