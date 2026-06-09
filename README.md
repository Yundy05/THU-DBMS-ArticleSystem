# THU-DBMS-ArticleSystem

Distributed Database Management System course project for Tsinghua University.  
This project implements a distributed database system across **four MongoDB nodes** for managing structured and unstructured article data, including users, articles, reads, derived engagement tables, and popularity rankings — with hot standby failover, Redis caching, expansion node support, and HDFS archival export.

---

## Overview

The system manages five core tables:

| Table | Fragmentation rule |
|---|---|
| `User` | By region (Beijing → DB1, Hong Kong → DB2) |
| `Article` | By category (science → DB1+DB2 replica, technology → DB2) |
| `Read` | Follows `User` fragmentation |
| `Be-Read` | Fragmented with duplication across DB1 and DB2 |
| `Popular-Rank` | By temporal granularity (daily → DB1, weekly/monthly → DB2) |

---

## Tech stack

- **Python 3.11+**
- **MongoDB 7** — four-node distributed cluster (DB1, DB2, DB3 hot standby, DB4 expansion)
- **Redis 7** — TTL-based read-through cache for article lookups and popular rankings
- **Docker / Docker Compose** — containerised services with optional profiles
- **Flask** — live web demo with query routing, monitoring, and popular rankings
- **PyMongo** — MongoDB driver
- **HDFS (Apache Hadoop 3)** — archival export layer for read logs and user data *(optional profile)*

---

## Architecture

```text
┌─────────────────────────────────────────────────────┐
│                  Distributed Data Center             │
│                                                     │
│  MongoDB1 (Beijing)  ──┐                            │
│  MongoDB2 (Hong Kong)  ├──► Flask App (OLTP)        │
│  MongoDB3 (Hot Standby)│        ↕                   │
│  MongoDB4 (Expansion)──┘   Redis Cache              │
│                                  ↕                  │
│              export_reads_to_hdfs.py                │
│                                  ↕                  │
│         HDFS NameNode + DataNode (archival)         │
└─────────────────────────────────────────────────────┘
```

---

## Repository structure

```text
THU-DBMS-ArticleSystem/
├── db-generation/               # generated data, text, image, video files
│   ├── user.dat
│   ├── article.dat
│   ├── read.dat
│   ├── image/
│   └── bbc_news_texts/
├── scripts/                     # all database scripts
│   ├── init_db.py               # create indexes on all nodes
│   ├── load_users.py            # fragment and load users
│   ├── load_articles.py         # fragment and load articles
│   ├── load_reads.py            # fragment and load reads
│   ├── derive_beread.py         # derive Be-Read table
│   ├── derive_popular_rank.py   # derive Popular-Rank table
│   ├── sync_standby.py          # sync DB1 → DB3 (hot standby)
│   ├── migrate_to_mongo4.py     # migrate data to expansion node
│   └── export_reads_to_hdfs.py  # export MongoDB → HDFS
├── src/db/
│   └── connections.py           # connection routing and node_status()
├── webapp/
│   ├── app.py                   # Flask application
│   └── templates/               # Jinja2 templates
├── bootstrap.sh                 # first-time setup script
├── reset_and_load.sh            # full reset and reload script
├── test_read_insert.sh          # test read insert across nodes
├── test_cache.sh                # demonstrate Redis caching performance
├── test_hdfs.sh                 # demonstrate HDFS export pipeline
├── docker-compose.yml
├── requirements.txt
├── .env
└── README.md
```

---

## Quick start
## Ensure to start run the genTable scripts from /db-generation and that files:
# article.dat, read.dat and user.dat are present


```bash
./bootstrap.sh
python webapp/app.py
```

Then open: [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## Full setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file:

```env
MONGO1_URI=mongodb://localhost:27017
MONGO2_URI=mongodb://localhost:27018
MONGO3_URI=mongodb://localhost:27019
MONGO4_URI=mongodb://localhost:27020
DB_NAME=distrib_db
REDIS_URI=redis://localhost:6379
CACHE_TTL=60
HDFS_URL=http://localhost:9870
HDFS_USER=hadoop
```

### 3. Start core services (MongoDB + Redis)

```bash
docker compose up -d
docker ps
```

### 4. Initialize indexes

```bash
python scripts/init_db.py
```

### 5. Load source data

```bash
python scripts/load_users.py db-generation/user.dat
python scripts/load_articles.py
python scripts/load_reads.py
```

### 6. Derive computed tables

```bash
python scripts/derive_beread.py
python scripts/derive_popular_rank.py
```

### 7. Sync hot standby

```bash
python scripts/sync_standby.py
```

### 8. Start the web demo

```bash
python webapp/app.py
```

---

## Helper scripts

### Bootstrap everything (first-time setup)

```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

### Full reset and reload

```bash
chmod +x reset_and_load.sh
./reset_and_load.sh
```

### Test read insert across nodes

```bash
chmod +x test_read_insert.sh
./test_read_insert.sh {uid} {aid}
# Example: ./test_read_insert.sh 0 1000
```

### Test Redis caching performance

```bash
chmod +x test_cache.sh
./test_cache.sh
# Compares cold vs warm request times and shows hit/miss stats
```

### Test HDFS export pipeline

```bash
chmod +x test_hdfs.sh
./test_hdfs.sh
# Starts HDFS, exports a 5000-doc sample, lists contents
```

---

## Optional features

### Expansion node (MongoDB4)

Starts a fourth MongoDB node as a data migration target:

```bash
docker compose --profile expansion up -d
./bootstrap.sh   # automatically detects and migrates to DB4
```

MongoDB4 appears on the `/monitor` page and shows migrated data counts.

### HDFS archival export

Starts Hadoop HDFS and exports all read logs, users, and articles:

```bash
docker compose --profile hdfs up -d
python scripts/export_reads_to_hdfs.py          # export all
python scripts/export_reads_to_hdfs.py --limit 5000  # export sample
python scripts/export_reads_to_hdfs.py --list        # list HDFS contents
```

HDFS Web UI: [http://localhost:9870](http://localhost:9870)

---

## Docker commands

```bash
# Core stack (MongoDB x3 + Redis)
docker compose up -d

# With expansion node
docker compose --profile expansion up -d

# With HDFS archival layer
docker compose --profile hdfs up -d

# With everything
docker compose --profile expansion --profile hdfs up -d

# Stop (keep data)
docker compose down

# Full reset (delete all data)
docker compose --profile expansion --profile hdfs down -v
```

---

## Web demo pages

| Page | URL | Description |
|---|---|---|
| Home | `/` | Article feed with popular rankings |
| Article | `/article/<aid>` | Full article detail, images, text |
| Queries | `/queries` | Live distributed query demo with routing map |
| Monitor | `/monitor` | Node status, replica consistency, Redis cache stats, rankings |

---

## Demonstrated features

| Feature | Implementation |
|---|---|
| Bulk load & fragmentation | `load_users.py`, `load_articles.py`, `load_reads.py` |
| Derived tables | `derive_beread.py`, `derive_popular_rank.py` |
| Distributed queries | Q1–Q6 on `/queries`, cross-node join on Q5 |
| Hot standby failover | DB3 mirrors DB1; `db1_or_standby()` routes automatically |
| Node monitoring | `/monitor` — live status, collection counts, consistency checks |
| Expansion node | MongoDB4 via Docker profile, `migrate_to_mongo4.py` |
| Redis caching | TTL cache for article lookups and popular rankings |
| HDFS archival | `export_reads_to_hdfs.py` — JSONL export respecting fragmentation |

---

## Troubleshooting

### Containers not running

```bash
docker ps
docker compose up -d
```

### Database connection error

Verify `.env` contains all five URIs:

```env
MONGO1_URI=mongodb://localhost:27017
MONGO2_URI=mongodb://localhost:27018
MONGO3_URI=mongodb://localhost:27019
MONGO4_URI=mongodb://localhost:27020
DB_NAME=distrib_db
```

### Popular-Rank or Be-Read missing

```bash
python scripts/derive_beread.py
python scripts/derive_popular_rank.py
```

### Redis not connecting

```bash
docker ps | grep redis
docker compose up -d redis
docker exec redis redis-cli ping   # should return PONG
```

### HDFS export failing

```bash
docker ps | grep namenode
docker compose --profile hdfs up -d
# Wait ~20 seconds for namenode to leave safe mode, then retry
```

### Website loads but no images or text

Check generated files exist:

```bash
ls db-generation/image/
ls db-generation/bbc_news_texts/
```

---

## Notes

This project satisfies the course requirements for bulk loading, distributed fragmentation, derived data generation, efficient query execution, node monitoring, hot standby failover, and server expansion in a distributed database environment.
