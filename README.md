# THU-DBMS-ArticleSystem
Distributed Database Management system for the selection, insert and more of various databases. Following along the requirements given by the Tsinghua University - Distributed Database Management System Course.

# Installation Guide
Install dependencies from root with "pip install -r requirements.txt"

# Starting Docker from inside the project folder
docker compose up -d

# Verify both are running
docker ps

# Additional Docker Commands
docker compose down          # stop but keep data
docker compose down -v       # stop and delete all data (full reset)

# Setting up Database indexes 
python scripts/init_db.py

# Loading users
python scripts/load_users.py db-generation/user.dat

# Loading BeReads
python scripts/derive_beread.py

# Loading Popular Rankings
python scripts/derive_popular_rank.py

# Loading Queries
python scripts/run_queries.py

# Loading Monitor
python scripts/monitor.py

# How to excute code
chmod +x bootstrap.sh
./bootstrap.sh

# Full reset and load
chmod +x reset_and_load.sh
./reset_and_load.sh