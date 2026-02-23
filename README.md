# System Design Lab

System design learning platform for:

- entering functional/non-functional requirements
- generating a testable system model (architecture variant + target profile)
- running sandboxed load tests
- monitoring live metrics
- receiving metric-driven technology recommendations

## Current Status

Implemented (MVP):

- Requirements -> generated variant -> testable synthetic target profile
- Scenario/requirements/variant persistence
- Run lifecycle state management and persisted run metrics/events
- Live dashboard with SSE metric streaming and charts
- Stop run action
- Metric-driven recommendations (Redis/Kafka/Elasticsearch/API gateway style suggestions)
- Sandbox backends:
  - `process`
  - `container` (real Docker sibling target + loadgen containers)
- Dockerized local run path

## Run The App (Docker)

The project is configured to run with Docker Compose.

### Ports

- Frontend: `http://localhost:15174`
- Backend API: `http://localhost:18010`
- Backend health: `http://localhost:18010/healthz`

### Start

```powershell
docker compose up -d --build
```

### Stop

```powershell
docker compose down
```

### Logs

```powershell
docker compose logs -f backend
docker compose logs -f frontend
```

## How To Use

1. Open `http://localhost:15174`
2. In `Scenario Builder`:
   - enter functional requirements (one per line)
   - enter non-functional requirements as `key: value` (example: `throughput_rps: 5000`)
   - click `Generate Testable System`
3. In `Run Monitor`:
   - review auto-filled `scenario_id` / `variant_id`
   - choose `Sandbox Backend` (`process` or `container`)
   - choose `Profile Type` (constant/ramp/spike/step/soak)
   - click `Start Run`
4. Watch live charts and recommendations

## Notes

- The generated “product” is currently a **testable synthetic target profile**, not full application code generation.
- In `container` sandbox mode, the system launches:
  - a generated HTTP target service container
  - a real request generator container
- Dashboard metrics are still driven by the backend simulation pipeline (container loadgen emits real metrics to container logs, but those logs are not yet ingested into the UI pipeline).

## Structure

- `backend/` Python API + orchestration services (FastAPI)
- `frontend/` React UI (Vite)
- `shared/` cross-service schemas/examples/contracts
- `docs/` requirements, roadmap, architecture
- `scripts/` helper scripts

## Next Recommended Steps

1. Ingest real container loadgen + Docker stats metrics into the dashboard pipeline
2. Generate multiple architecture variants from the same requirements
3. Add structured NFR forms and validation
4. Build comparison reports (baseline vs modified variant)
