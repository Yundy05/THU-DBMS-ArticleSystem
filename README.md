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