.PHONY: run test lint format clean docker-build

run:
	cd Backend && python run.py

test:
	pytest Backend/tests/ -v

lint:
	ruff check Backend/app

format:
	ruff format Backend/app

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker-compose build
