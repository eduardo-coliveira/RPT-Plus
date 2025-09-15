run_api:
	@uvicorn backend.app:app

run_server:
	@cd vite-frontend && npm run dev & sleep 2 && (xdg-open http://localhost:5173/ || open http://localhost:5173/ || start http://localhost:5173/)

all: run_server run_api