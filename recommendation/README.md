# Offline data preparation and popular baseline

This is the first recommendation milestone inside the existing Java repository. It prepares LiveRec's historical observations and evaluates a training-only popular-channel baseline. It does not train a neural model or start an API service yet.

## Data source

Download the Twitch100k CSV from the Drive folder linked in [LiveRec's dataset documentation](https://github.com/JRappaz/liverec#datasets). The publicly available file was named `100k_a.csv` at download time; the source loader describes `100k.csv`. Keep the actual downloaded name and checksum in the manifest. Put it at `data/raw/100k_a.csv`. Do not commit or redistribute raw data. Cite Rappaz, McAuley, and Aberer's RecSys 2021 paper in research uses, following the source's citation request.

The CSV has five headerless columns: anonymized user, broadcast ID, channel name, first observation round, last observation round. These are implicit chat-presence observations, not clicks or proof of continuous watching. The documentation describes ten-minute rounds. This milestone treats start/stop as inclusive observed endpoints and excludes intervals crossing split cutoffs.

## Local Python execution

From the repository root, using Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r recommendation/requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m recommendation.prepare_data --input data/raw/100k_a.csv --output data/prepared-v001
.venv/bin/python -m recommendation.evaluate --prepared data/prepared-v001 --output artifacts/baseline-validation-v001
```

Configuration is read from `recommendation/config.yaml`. Supply `--config` for another YAML file; explicit `--max-users`, `--seed`, and `--k` flags override corresponding file values. Defaults sample up to 5,000 users with seed 42 and evaluate K=10,200. Output directories must be empty or new; use new version directories for subsequent runs.

## Container execution

Docker must be installed and running. These commands are prepared but have not been verified on the current laptop, where Docker is unavailable.

```bash
docker build -f recommendation/Dockerfile -t twitch-offline .
docker run --rm twitch-offline -m pytest -q
docker run --rm -v "$PWD/data:/app/data" twitch-offline -m recommendation.prepare_data --input /app/data/raw/100k_a.csv --output /app/data/prepared-v001
docker run --rm -v "$PWD/data:/app/data:ro" -v "$PWD/artifacts:/app/artifacts" twitch-offline -m recommendation.evaluate --prepared /app/data/prepared-v001 --output /app/artifacts/baseline-validation-v001
```

Create the host `data/` and `artifacts/` directories first. Training and preparation are one-off container jobs; this image's entry point is Python, not Uvicorn. The later serving container will load a model bundle separately.

## Outputs and evaluation

Preparation writes train/validation/test Parquet, training-only identity mappings, and a manifest. Global timeline cutoffs use 70%/85% of the cleaned source observation range before sampling. Exact duplicates are removed; separate repeated observations remain. Seed-based SHA-256 ordering selects users independently of input-row order. The user population includes future-only users, reported as cold-start coverage.

Baseline popularity counts distinct training users per channel, breaking ties by channel name. The validation query is one recommendation list per eligible training-known user; relevance is distinct validation-period channels within the training catalog. Previously observed channels remain eligible. Recall/NDCG are averaged equally across eligible users. Users without eligible labels and unseen identities are reported separately, so these metrics do not imply performance for every validation user or every channel. No historical live-availability filter is applied.

`validation_report.json` records metrics, coverage denominators, protocol, source and prepared-file checksums, seed, and timeline. `popular_channels.json` contains the full ordered training catalog. Channel IDs are bundle-local embedding indices, not Twitch numeric IDs. The test split is created but is not consumed by the baseline validation evaluator.

The current laptop run passed 13 Python tests. Java files are unchanged; Java build verification and Docker runtime verification are not included in that claim.
