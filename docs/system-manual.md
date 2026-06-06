# System Manual

**Course:** Distributed Database Management Systems 2026  
**Author:** Andy Yu 俞澎  
**Institution:** Tsinghua University  

---

## 1. System Overview

THU-DBMS-ArticleSystem is a distributed database system managing article data across multiple MongoDB nodes. The system implements horizontal fragmentation, hot standby failover, Redis caching, expansion node migration, and HDFS archival export.

### 1.1 Architecture Summary

```text
┌───────────────────────────────────────────────────┐
│                 Distributed Data Center           │
│                                                   │
│  MongoDB1 (Beijing)   ──┐                         │
│  MongoDB2 (Hong Kong)   ├──► Flask Web App        │
│  MongoDB3 (Hot Standby) │        ↕                │
│  MongoDB4 (Expansion) ──┘   Redis Cache           │
│                                  ↕                │
│              export_reads_to_hdfs.py              │
│                                  ↕                │
│        HDFS NameNode + DataNode (archival)        │
└───────────────────────────────────────────────────┘
```

### 1.2 Node Responsibilities

| Node     | Role                 | Data held                                                                                         |
|----------|----------------------|---------------------------------------------------------------------------------------------------|
| MongoDB1 | Beijing data center  | Beijing users, science articles replica, Beijing reads, science Be-Reads, daily popular rank     |
| MongoDB2 | Hong Kong data center | HK users, all articles, HK reads, all Be-Reads, weekly/monthly popular rank                     |
| MongoDB3 | Hot standby          | Full mirror of MongoDB1 – automatic failover                                                     |
| MongoDB4 | Expansion node       | Migration target – receives data from DB1 and DB2                                                |
| Redis    | Cache layer          | Article lookups and popular rankings (60s TTL)                                                   |
| HDFS     | Archival layer       | Historical read logs, users, articles as JSONL                                                   |

---

## 2. System Requirements

### 2.1 Hardware

| Component | Minimum                                |
|-----------|----------------------------------------|
| CPU       | 4 cores (Apple Silicon M1+ or x86-64) |
| RAM       | 8 GB (16 GB recommended)              |
| Disk      | 20 GB free                            |

### 2.2 Software

| Software        | Version | Purpose                       |
|-----------------|---------|-------------------------------|
| Docker Desktop  | 4.x+    | Container runtime             |
| Docker Compose  | 2.x+    | Multi-container orchestration |
| Python          | 3.11+   | Application runtime           |
| pip             | 23+     | Python package manager        |

### 2.3 Python dependencies

All dependencies are listed in `requirements.txt`. Key packages:

- `pymongo`
- `flask`
- `redis`
- `hdfs`
- `python-dotenv`

---

## 3. Installation

### 3.1 Clone the repository

```bash
git clone https://github.com/Yundy05/THU-DBMS-ArticleSystem.git

# Or via SSH:
git clone git@github.com:Yundy05/THU-DBMS-ArticleSystem.git

cd THU-DBMS-ArticleSystem
```

### 3.2 Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3.3 Configure environment

Create a `.env` file in the project root:

```env
MONGO1_URI=mongodb://localhost:27017
MONGO2_URI=mongodb://localhost:27018
MONGO3_URI=mongodb://localhost:27019
MONGO4_URI=mongodb://localhost:27020
DB_NAME=distrib_db
REDIS_URI=redis://localhost:6379
CACHE_TTL=60
HDFS_URL=http://localhost:9870
HDFS_USER=root
```

### 3.4 Configure `/etc/hosts` (required for HDFS only)

```bash
echo "127.0.0.1 namenode" | sudo tee -a /etc/hosts
echo "127.0.0.1 datanode" | sudo tee -a /etc/hosts
```

> Note: The project was tested and used on a macOS machine; Windows/Linux behaviour has not been fully verified.

---

## 4. Configuration

### 4.1 Docker Compose profiles

The system uses Docker Compose profiles to separate optional services:

| Profile  | Services started              | Command                                        |
|----------|--------------------------------|------------------------------------------------|
| *(none)* | MongoDB1–3 + Redis            | `docker compose up -d`                         |
| `expansion` | + MongoDB4                 | `docker compose --profile expansion up -d`     |
| `hdfs`   | + HDFS NameNode + DataNode    | `docker compose --profile hdfs up -d`          |

### 4.2 Environment variables

| Variable    | Default                   | Description                     |
|-------------|---------------------------|---------------------------------|
| `MONGO1_URI`| mongodb://localhost:27017 | Beijing node URI               |
| `MONGO2_URI`| mongodb://localhost:27018 | Hong Kong node URI             |
| `MONGO3_URI`| mongodb://localhost:27019 | Hot standby URI                |
| `MONGO4_URI`| mongodb://localhost:27020 | Expansion node URI             |
| `DB_NAME`   | distrib_db                | MongoDB database name          |
| `REDIS_URI` | redis://localhost:6379    | Redis connection URI           |
| `CACHE_TTL` | 60                        | Cache TTL in seconds           |
| `HDFS_URL`  | <http://localhost:9870>     | HDFS NameNode WebHDFS URL      |
| `HDFS_USER` | root                      | HDFS user for writes           |

---

## 5. Operation

### 5.1 First-time bootstrap

Run the bootstrap script to start all containers, load all data, and sync the standby:

```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

This performs the following steps automatically:

- Starts Docker containers  
- Waits for all MongoDB nodes to be ready  
- Waits for Redis to be ready  
- Initialises indexes on all nodes  
- Loads users, articles, and reads (fragmented by region/category)  
- Derives Be-Read and Popular-Rank tables  
- Syncs MongoDB1 → MongoDB3 (hot standby)  
- Migrates data to MongoDB4 if the expansion profile is active  

### 5.2 Start the web application

```bash
python webapp/app.py
```

The application starts on: <http://127.0.0.1:5001>

### 5.3 Web interface pages

| Page          | URL                                   | Description                            |
|---------------|----------------------------------------|----------------------------------------|
| Home          | <http://127.0.0.1:5001/>              | Article feed and popular rankings      |
| Article detail| `http://127.0.0.1:5001/article/<aid>` | Full article with images and text      |
| Query demo    | <http://127.0.0.1:5001/queries>       | Live distributed query routing demo    |
| Monitor       | <http://127.0.0.1:5001/monitor>       | Node status, consistency, cache stats  |

### 5.4 Full reset and reload

To wipe all data and reload from source files:

```bash
chmod +x reset_and_load.sh
./reset_and_load.sh
```

---

## 6. Scripts Reference

### 6.1 Initialisation scripts

| Script                  | Usage                                              | Description                               |
|-------------------------|----------------------------------------------------|-------------------------------------------|
| `scripts/init_db.py`    | `python scripts/init_db.py`                        | Creates indexes on all nodes              |
| `scripts/load_users.py` | `python scripts/load_users.py db-generation/user.dat` | Loads and fragments users by region   |
| `scripts/load_articles.py` | `python scripts/load_articles.py`              | Loads and fragments articles by category  |
| `scripts/load_reads.py` | `python scripts/load_reads.py`                    | Loads and fragments reads by user region  |

### 6.2 Derivation scripts

| Script                      | Usage                                 | Description                                       |
|-----------------------------|----------------------------------------|---------------------------------------------------|
| `scripts/derive_beread.py`  | `python scripts/derive_beread.py`     | Derives Be-Read engagement table                  |
| `scripts/derive_popular_rank.py` | `python scripts/derive_popular_rank.py` | Derives daily/weekly/monthly popular rankings |

### 6.3 Maintenance scripts

| Script                         | Usage                                   | Description                         |
|--------------------------------|------------------------------------------|-------------------------------------|
| `scripts/sync_standby.py`      | `python scripts/sync_standby.py`        | Syncs MongoDB1 → MongoDB3           |
| `scripts/migrate_to_mongo4.py` | `python scripts/migrate_to_mongo4.py`   | Migrates data to expansion node     |
| `scripts/export_reads_to_hdfs.py` | `python scripts/export_reads_to_hdfs.py` | Exports MongoDB data to HDFS   |

### 6.4 HDFS export options

```bash
# Export all documents
python scripts/export_reads_to_hdfs.py

# Export sample (5000 docs per collection)
python scripts/export_reads_to_hdfs.py --limit 5000

# List existing HDFS exports
python scripts/export_reads_to_hdfs.py --list
```

---

## 7. Testing and Demonstration

### 7.1 Test read insert across nodes

```bash
chmod +x test_read_insert.sh
./test_read_insert.sh <uid> <aid>

# Example
./test_read_insert.sh 0 1000
```

Verifies that a read event is written to the correct MongoDB node (DB1 for Beijing users, DB2 for Hong Kong users) and reflected in the Be-Read table.

### 7.2 Test Redis caching

```bash
chmod +x test_cache.sh
./test_cache.sh
```

Compares cold (cache miss) vs warm (cache hit) response times and prints Redis hit/miss statistics. Expected output shows response time dropping significantly on the second request.

### 7.3 Test HDFS export

```bash
chmod +x test_hdfs.sh
./test_hdfs.sh
```

Starts HDFS, exports a 5000-document sample from each collection, verifies file contents, and prints the HDFS directory listing.

### 7.4 Demonstrate hot standby failover

```bash
# Step 1 — stop MongoDB1 to trigger failover
docker stop mongo1

# Step 2 — reload /queries or /monitor in browser
# MongoDB3 automatically takes over; node bar shows DB1 offline, DB3 online

# Step 3 — restore MongoDB1
docker start mongo1
python scripts/sync_standby.py
```

### 7.5 Demonstrate expansion node

```bash
# Start with expansion profile
docker compose --profile expansion up -d
./reset_and_load.sh

# MongoDB4 appears as "online" on /monitor with migrated data counts
```

---

## 8. Docker Commands Reference

```bash
# Start core stack (MongoDB x3 + Redis)
docker compose up -d

# Start with expansion node
docker compose --profile expansion up -d

# Start with HDFS
docker compose --profile hdfs up -d

# Start everything
docker compose --profile expansion --profile hdfs up -d

# Check running containers
docker ps

# View container logs
docker logs mongo1
docker logs redis
docker logs namenode

# Stop all (keep data)
docker compose down

# Full reset (delete all data volumes)
docker compose --profile expansion --profile hdfs down -v
```

---

## 9. Troubleshooting

### MongoDB not connecting

```bash
docker ps                  # check containers are running
docker compose up -d       # restart if needed
docker logs mongo1         # check for errors
```

Verify `.env` has all five URIs set correctly.

### Redis not responding

```bash
docker ps | grep redis
docker exec redis redis-cli ping   # should return PONG
docker compose up -d redis         # restart if needed
```

### Be-Read or Popular-Rank missing

```bash
python scripts/derive_beread.py
python scripts/derive_popular_rank.py
```

### Hot standby out of sync after DB1 recovery

```bash
python scripts/sync_standby.py
```

### HDFS namenode in safe mode

```bash
# Wait for automatic exit (~30s) or force exit
docker exec namenode hdfs dfsadmin -safemode leave
```

### HDFS datanode not resolving from host machine

```bash
# Ensure /etc/hosts entries exist
cat /etc/hosts | grep -E "namenode|datanode"

# Add if missing
echo "127.0.0.1 namenode" | sudo tee -a /etc/hosts
echo "127.0.0.1 datanode" | sudo tee -a /etc/hosts
```

### Website shows no images or text

```bash
ls db-generation/image/
ls db-generation/bbc_news_texts/
```

Generated asset files must exist in these directories.

---

## 10. Important File Structure Reference

```text
THU-DBMS-ArticleSystem/
├── db-generation/
│   ├── user.dat                     # raw user data
│   ├── article.dat                  # raw article data
│   ├── read.dat                     # raw read log data
│   ├── image/                       # article images
│   └── bbc_news_texts/              # article text files
├── scripts/
│   ├── init_db.py                   # index initialisation
│   ├── load_users.py                # user fragmentation + load
│   ├── load_articles.py             # article fragmentation + load
│   ├── load_reads.py                # read fragmentation + load
│   ├── derive_beread.py             # Be-Read derivation
│   ├── derive_popular_rank.py       # Popular-Rank derivation
│   ├── sync_standby.py              # DB1 → DB3 sync
│   ├── migrate_to_mongo4.py         # DB1+DB2 → DB4 migration
│   └── export_reads_to_hdfs.py      # MongoDB → HDFS export
├── src/db/
│   └── connections.py               # connection routing + node_status()
├── webapp/
│   ├── app.py                       # Flask application
│   └── templates/                   # Jinja2 HTML templates
├── bootstrap.sh                     # first-time setup
├── reset_and_load.sh                # full reset and reload
├── test_read_insert.sh              # read insert test
├── test_cache.sh                    # Redis cache demo
├── test_hdfs.sh                     # HDFS export demo
├── docker-compose.yml               # service definitions
├── requirements.txt                 # Python dependencies
├── .env                             # environment configuration
└── README.md                        # project overview
```
