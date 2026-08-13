SERVER = john@server-john

.PHONY: deploy logs status restart stop

deploy:
	bash scripts/deploy.sh

logs:
	ssh $(SERVER) 'journalctl -u vigilancia -f'

status:
	ssh $(SERVER) 'systemctl status vigilancia'

restart:
	ssh $(SERVER) 'sudo systemctl restart vigilancia'

stop:
	ssh $(SERVER) 'sudo systemctl stop vigilancia'
