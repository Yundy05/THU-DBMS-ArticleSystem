# THU-DBMS-ArticleSystem

Distributed Database Management System course project for Tsinghua University.  
This project implements a two-node distributed database system for managing structured and unstructured article data, including users, articles, reads, derived engagement tables, and popularity rankings. [file:19][file:21]

## Overview

The system manages five core tables:

- `User`
- `Article`
- `Read`
- `Be-Read`
- `Popular-Rank`

It follows the project fragmentation rules:

- `User` fragmented by region
- `Article` fragmented by category
- `Read` fragmented following `User`
- `Be-Read` fragmented with duplication
- `Popular-Rank` fragmented by temporal granularity 

## Tech stack

- Python
- MongoDB
- Docker / Docker Compose
- Flask (web demo)
- PyMongo

## Repository structure

```text
THU-DBMS-ArticleSystem/
├── db-generation/          # generated data, text, image, video files
├── scripts/                # initialization, load, derive, query, monitor scripts
├── src/db/                 # database connection and routing logic
├── webapp/                 # Flask demo website
├── docker-compose.yml
├── requirements.txt
├── .env
└── README.md
```

## Quick start

Run the whole project in this order:

```bash
pip install -r requirements.txt
docker compose up -d
python scripts/init_db.py
python scripts/load_users.py db-generation/user.dat
python scripts/load_articles.py db-generation/article.dat
python scripts/load_reads.py db-generation/read.dat
python scripts/derive_beread.py
python scripts/derive_popular_rank.py
python webapp/app.py
```

Then open:

```text
http://127.0.0.1:5001
```

## Full setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Docker services

```bash
docker compose up -d
docker ps
```

### 3. Initialize database and indexes

```bash
python scripts/init_db.py
```

### 4. Load source data

```bash
python scripts/load_users.py db-generation/user.dat
python scripts/load_articles.py db-generation/article.dat
python scripts/load_reads.py db-generation/read.dat
```

### 5. Derive computed tables

```bash
python scripts/derive_beread.py
python scripts/derive_popular_rank.py
```

### 6. Run query and monitoring scripts

```bash
python scripts/run_queries.py
python scripts/monitor.py
```

### 7. Start the web demo

```bash
pip install -r webapp/requirements-web.txt
python webapp/app.py
```

## Helper scripts

### Bootstrap everything

```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

### Full reset and reload

```bash
chmod +x reset_and_load.sh
./reset_and_load.sh
```

### Testing reading and inserting for given user id and article id into databases

```bash
chmod +x test_read_insert.sh
./test_read_insert.sh {uid} {aid} 
```


## Docker commands

```bash
docker compose up -d      # start containers
docker compose down       # stop containers, keep data
docker compose down -v    # stop containers and delete all data
docker ps                 # verify running containers
```

## Web demo

The Flask website provides:

- article browsing
- article detail pages
- image loading
- related text display
- node monitoring
- daily / weekly / monthly popular rankings

Start it with:

```bash
python webapp/app.py
```

## Troubleshooting

### Containers not running

```bash
docker ps
docker compose up -d
```

### Database connection error

Check `.env` contains:

```env
MONGO1_URI=...
MONGO2_URI=...
MONGO3_URI=...
DB_NAME=...
```

### Popular-Rank or Be-Read missing

Make sure these were executed:

```bash
python scripts/derive_beread.py
python scripts/derive_popular_rank.py
```

### Website loads but no images or text appear

Check that generated files exist under:

- `db-generation/image/`
- `db-generation/bbc_news_texts/`

## Notes

This project is designed to satisfy the course requirement for bulk loading, distributed fragmentation, derived data generation, query execution, and monitoring in a distributed database environment. 