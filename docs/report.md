## **Title** 

Design and Implementation of a Distributed Article Management System with Hot Standby, Redis Caching, and HDFS Archival 

## **Abstract** 

Modern content platforms must serve article data at low latency while preserving consistency and availability across distributed data centers. This project implements a distributed database management system (DDBMS) for an article reading application, based on four MongoDB nodes, Redis caching, and Hadoop HDFS for archival export. The system follows coursespecified horizontal fragmentation rules over five core tables (User, Article, Read, Be-Read, Popular-Rank) and extends them with hot standby failover, an expansion node for migration, and an analytical export pipeline. A Flask web application exposes live query and monitoring dashboards to visualize routing, node status, and cache behavior. Throughout development, practical challenges such as container orchestration, standby synchronization, HDFS connectivity on Apple Silicon, and Redis integration were resolved iteratively, influencing design choices. Experimental evaluation on a 1M‑record dataset demonstrates correct fragmentation, transparent failover, significant latency reduction via Redis caching, and successful export of 23,945 records to HDFS. 

## **1. Problem Background** 

Large-scale article platforms must manage millions of users and articles, each generating high volumes of read events, likes, comments, and shares. A single centralised database quickly becomes a bottleneck in such scenarios, limiting scalability and resilience. A distributed database system distributes data across multiple physical nodes, bringing data closer to users and improving both throughput and fault tolerance. 

The course project provides a realistic miniature of this problem. The data model consists of: 

- Users with geographic attributes (e.g., region). 

- Articles with categorical metadata (e.g., science, technology). 

- Read logs (user–article interactions). 

- Derived engagement statistics (Be-Read). 

- Derived popularity rankings (Popular-Rank). 

The project specification requires horizontal fragmentation based on region, category, and temporal granularity, as well as efficient query support over these distributed fragments. Beyond functional correctness, modern systems must address failover, caching, and analytical workloads, which motivated the extensions implemented in this work. 

## **2. Motivation** 

The project’s base requirement is to implement a distributed article system satisfying fragmentation and query rules for the course assignment. However, these minimal requirements would not reflect how real-world systems are engineered. Several additional motivations shaped the design: 

1. **High availability and resilience** 

Real systems cannot afford downtime when a primary node fails. Implementing a hot standby (MongoDB3) for MongoDB1 demonstrates failover behavior and resilience under node loss, aligning with industry practices for distributed databases. 

## 2. **Performance through caching** 

The professor explicitly encouraged using “latest technologies,” which naturally suggested adding Redis caching as an independent, production-grade cache layer. Caching is a standard pattern for reducing repeated reads from a distributed database, especially for popular content and ranking queries. 

## 3. **Scalability and future growth** 

The “expansion node” (MongoDB4) models real data center expansion: onboarding a new node and migrating data gradually without stopping the system. This allowed exploration of data migration scripts, monitoring updates, and UI changes for new capacity. 

## 4. **Analytical capabilities beyond OLTP.** 

Modern architectures frequently combine an operational store with a batch or archival layer (often in HDFS or cloud object storage). Implementing a MongoDB → HDFS export pipeline shows how read logs can be offloaded for offline analytics, aligning with Lambda-style architectures. 

## 5. **Observability and demonstration.** 

The course grading and presentation benefit from visual explanations. Building /monitor and /queries pages that expose routing, workloads, replication, cache status, and HDFS exports made it easier to debug issues during development and to “prove” behaviors are operational. 

These motivations drove the decision to go beyond a two-node setup and incorporate Redis, a hot standby, an expansion node, and HDFS export. 

## **3. Existing Solutions** 

Distributed databases and related technologies provide several conceptual building blocks relevant to this project: 

## 1. **Distributed DBMS and fragmentation.** 

Classic DDBMS literature describes horizontal fragmentation by predicates (e.g., perregion, per-category) and derived replication to satisfy locality and redundancy requirements. Commercial systems like MongoDB sharding, Cassandra, and CockroachDB all partition data across nodes and maintain a “global” abstraction over multiple physical instances. 

## 2. **High availability via replication/standby.** 

Many databases support replica sets and failover. MongoDB’s replica sets, PostgreSQL streaming replication, and MySQL primary–replica setups are typical examples. Some production architectures also dedicate a hot standby for a primary region, ready to take over if the primary fails. 

## 3. **Caching with Redis.** 

Redis is widely used as an in-memory cache sitting between application servers and databases. Patterns such as read-through caching and TTL-based eviction are standard for reducing latency on repeated queries and minimizing load on databases. 

## 4. **HDFS and analytical layers.** 

Hadoop HDFS is a standard distributed file system for large-scale batch analytics. The Lambda architecture proposes a dual structure: a fast path for real-time views and a batch path for historical analysis, with master data often stored in HDFS. 

## 5. **Web front-ends with Flask and MongoDB.** 

Many tutorials and frameworks (e.g., Flask+PyMongo, Eve) show how to integrate MongoDB with Flask for web APIs and dashboards. These solutions focus on CRUD and single-node MongoDB, with less emphasis on multi-node fragmentation and failover. 

Existing solutions informed design decisions but could not be adopted “as-is” because the course required a specific fragmentation model and a custom multi-node layout. Instead, the project adapts these ideas into a bespoke four-node MongoDB topology plus Redis and HDFS. 

## **4. Problem Definition** 

The problem can be divided into core and extended objectives. 

## **4.1 Core objectives** 

Given five logical tables (User, Article, Read, Be-Read, Popular-Rank) and a set of fragmentation rules, design and implement a distributed database system that: 

1. Physically stores data across at least two MongoDB instances according to: 

   - User: fragmented by region (Beijing vs. Hong Kong). 

   - Article: fragmented by category (science vs. technology, with some replication). 

   - Read: fragmented by following User’s region. 

   - Be-Read: fragmented with duplication across nodes. 

   - Popular-Rank: fragmented by temporal granularity (daily vs. weekly/monthly). 

2. Supports efficient queries that respect the fragmentation rules and minimize unnecessary cross-node traffic. 

3. Provides scripts for bulk loading, derived table generation, and basic monitoring. 

## **4.2 Extended objective** 

Beyond the base requirements, the project aims to: 

1. Implement **hot standby failover** for MongoDB1 using MongoDB3, with transparent routing at the application level and a monitoring UI to visualize failover. 

2. Add a **Redis cache** layer to accelerate frequently accessed data (article metadata and popular rankings), with cache invalidation on writes and statistics displayed on /monitor. 

3. Introduce an **expansion node (MongoDB4)** and migration workflow, including: 

   - Starting MongoDB4 via a Docker profile. 

   - Migrating selected data from DB1/DB2 to DB4. 

   - Visualizing its presence in monitoring and query pages. 

4. Provide an **HDFS export pipeline** that periodically exports MongoDB data (reads, users, articles) to HDFS in JSONL format, preserving fragmentation distinctions. 

5. Document installation, configuration, and operation in a separate system manual and produce a research-style report describing design and evaluation. 

## **5. Proposed Solution** 

The solution is a custom DDBMS built on top of MongoDB, Flask, Redis, Docker, and HDFS. It decomposes into several components. 

## **5.1 Data model and fragmentation** 

The logical schema is implemented in MongoDB collections: 

- users 

- articles 

- reads 

- bereads 

- ● popular_rank 

Fragmentation rules are implemented in loader and derivation scripts: 

- **User fragmentation:** 

load_users.py routes each user document to MongoDB1 (Beijing) or MongoDB2 (Hong Kong) based on the region field. 

- **Article fragmentation:** 

load_articles.py ensures science articles are available on both DB1 and DB2 (replica), whereas technology articles are stored only on DB2, following the assignment’s rules. 

- **Read fragmentation:** 

load_reads.py routes reads to DB1 or DB2 by looking up the user’s region, aligning reads with the user’s home data center. 

- **Be-Read derivation:** 

derive_beread.py aggregates reads into Be-Read statistics (counts of reads, agrees, comments, shares) and stores them on both DB1 and DB2, providing duplication. 

## ● **Popular-Rank derivation:** 

derive_popular_rank.py computes daily, weekly, and monthly rankings. Daily rankings are stored on DB1; weekly and monthly rankings are stored on DB2. 

This fragmentation model was chosen to align with the given rules while matching a plausible design: region-based partitioning for users/reads and category/temporal-based partitioning for articles and rankings. 

## **5.2 Connection routing and hot standby** 

A central module src/db/connections.py encapsulates all MongoDB connection logic: 

- get_mongo1(), get_mongo2(), get_mongo3(), get_mongo4() create and reuse MongoDB clients. 

- node_status() pings each node and returns statuses (online, standby, offline) used by the UI. 

- _which_db1_node() returns either "MongoDB1" or "MongoDB3" based on MongoDB1’s health. 

- db1_or_standby() returns a database handle pointing to DB1 by default, or DB3 when DB1 is offline. 

Application code in webapp/app.py uses db1_or_standby() for all “DB1” operations. This design decouples failover logic from business logic: individual queries do not need to know whether DB1 or DB3 is currently active. During development, this abstraction was introduced after realising that manually branching on failover in each route would be error-prone and repetitive. 

## **5.3 Flask web application and monitoring** 

The Flask app provides two main UI pages relevant to the distributed design: 

1. **Query demo (/queries).** 

   - Shows a **node status bar** with MongoDB1–4 statuses (including DB3 hot standby and DB4 expansion). 

   - Presents a **routing map** explaining which query runs on which node. 

   - Executes live queries on every page load: 

      - Beijing users (DB1 or DB3). 

      - Hong Kong users (DB2). 

      - Science/technology articles (DB2). 

      - A cross-node join combining user, reads, and articles. 

      - Popular rankings (daily from DB1/DB3, weekly/monthly from DB2). 

2. **Monitor page (/monitor).** 

   - **Server overview:** shows each MongoDB node’s status, role, and collection counts (users, articles, reads, bereads, popular_rank), including DB4. 

   - **Managed data breakdown:** per-node distribution of users (by region), articles (by category), and popular_rank entries (by temporal granularity). 

   - **Workload summary:** counts of records per node, validating fragmentation and load distribution. 

   - **Replica consistency:** compares counts for replicated datasets (science articles, Be-Reads, Popular-Rank) and the DB1→DB3 standby sync. 

   - **Redis cache stats:** shows TTL, live keys, hits, misses, and evictions, demonstrating cache activity. 

   - **Popular rankings:** renders top articles for daily/weekly/monthly rankings with images and metadata. 

These pages were developed iteratively in response to debugging needs: when fragmentation or failover did not behave as expected, additional metrics and explanatory labels were added until the system’s behavior was transparent. 

## **5.4 Redis caching design** 

Redis is integrated as a read-through cache between Flask and MongoDB: 

- A redis service is added to docker-compose.yml. 

- REDIS_URI and CACHE_TTL are configured in .env. 

- In webapp/app.py, helper functions abstract caching: 

   - _cache_get(key) retrieves a JSON-serialized value from Redis and deserializes it. 

   - _cache_set(key, value) serializes and stores data with a TTL. 

   - cache_clear() is called after writes to invalidate stale data. 

- Two key functions use the cache: 

   - article_lookup(aid) caches article metadata. 

   - latest_ranks() caches the enriched popular rankings for daily/weekly/monthly. 

The design choice was to cache only read-intensive, relatively small datasets: article metadata and ranking results. This avoids overcomplicating invalidation logic while giving measurable performance benefits. A dedicated test_cache.sh script measures cold vs. warm request times and prints Redis hit/miss statistics, helping to justify caching in the evaluation. 

## **5.5 Expansion node and migration** 

MongoDB4 is added as an **expansion node** : 

- mongo4 is defined in docker-compose.yml under an expansion profile. 

- get_mongo4() and associated helpers allow the application to connect to DB4. 

- The monitor and queries pages display DB4 status as an “expansion” node, clarifying that it is not part of the main query routing path. 

- A script migrate_to_mongo4.py copies selected collections from DB1 and DB2 to DB4, simulating an online data center expansion. 

- Bootstrap and reset scripts (bootstrap.sh, reset_and_load.sh) conditionally wait for mongo4 if it is running and then trigger migration. 

This feature was added after the core system was working, to demonstrate the ability to onboard new capacity without changing existing fragmentation logic or downtime. 

## **5.6 HDFS export pipeline** 

To support archival and analytics, export_reads_to_hdfs.py exports MongoDB data to Hadoop HDFS: 

- HDFS services (namenode, datanode) are defined under a hdfs profile in dockercompose.yml. 

- The script uses the Python hdfs client and WebHDFS to write JSONL files. 

- HDFS_URL, HDFS_USER, and base path /project/distrib_db are configurable. 

- Export preserves fragmentation semantics: 

   - reads/beijing_reads_<timestamp>.jsonl from DB1. 

   - reads/hongkong_reads_<timestamp>.jsonl from DB2. 

   - users/beijing_users_<timestamp>.jsonl, users/hongkong_users_<timestamp>.jsonl. 

   - articles/articles_<timestamp>.jsonl from DB2. 

On macOS/ARM, integrating HDFS required additional work: choosing compatible Docker images, handling WebHDFS redirects that referenced internal hostnames (datanode), and adjusting /etc/hosts. A test_hdfs.sh script automates starting HDFS, exporting a sample of 5000 documents per collection, and listing files to verify success. The HDFS web UI confirms that 23,945 documents were exported and stored in 5 blocks. 

## **6. Solution Evaluation** . 

## **6.1 Fragmentation and replication correctness** 

Using the /monitor and /queries pages combined with direct MongoDB shell commands, the following were verified: 

- **User fragmentation:** DB1 contains only Beijing users; DB2 contains only Hong Kong users. Counts on the monitor page and sample queries Q1/Q2 confirm this. 

- **Article fragmentation:** Science articles appear on DB2 (and replicated to DB1 as required), while technology articles reside on DB2. Q3/Q4 show correct subsets, and the monitor’s “Articles by category” counts match expectations. 

- **Read fragmentation:** For a Beijing user, reads go to DB1 (or DB3 during failover); for a Hong Kong user, reads go to DB2. The test_read_insert.sh script inserts a read via the Flask endpoint and then checks DB1/DB3/DB2 to confirm correct placement. 

- **Be-Read replication:** Be-Read documents for a given article appear on both DB1 and DB2, with DB2 often having greater or equal counts due to additional categories. The replica consistency section checks that bereads.db1 <= bereads.db2. 

- **Popular-Rank fragmentation:** The monitor checks that daily ranks exist on DB1, while weekly and monthly rankings are on DB2. The /queries page displays rankings with the node label for each granularity. 

## **6.2 Failover behavior** 

Failover was tested by: 

1. Starting the full stack and loading data. 

2. Stopping MongoDB1 (docker stop mongo1). 

3. Reloading /queries and /monitor. 

Observations: 

- The node status bar marks MongoDB1 as offline and MongoDB3 as online. 

- Queries Q1 (Beijing users) and related “daily popular rank” automatically switch to DB3 via db1_or_standby(), with the UI labeling DB3 as the serving node. 

- Be-Read and ranking data for science articles remain accessible because DB3 mirrors DB1’s data after running sync_standby.py. 

This confirms that the application can tolerate DB1 failure without user-visible errors on core queries. 

## **6.3 Redis caching performance** 

The test_cache.sh script demonstrates caching behavior: 

- Redis is flushed at the start (FLUSHDB). 

- The monitor page /monitor is requested twice using curl, with execution time measured. 

- Redis INFO shows keyspace_hits and keyspace_misses. 

In practice, the first request is significantly slower (hitting MongoDB multiple times to fetch popular rankings and article metadata), while the second request is faster because latest_ranks() and article_lookup() hit Redis instead of MongoDB. This provides concrete evidence that caching reduces read latency and load on MongoDB for repeated requests. 

## **6.4 HDFS export verification** 

Running test_hdfs.sh on macOS produced the following: 

- Successful export of 5,000 reads from Beijing, 5,000 reads from Hong Kong, 5,000 articles, and all users respecting fragmentation limits, totaling 23,945 documents. 

- HDFS CLI (hdfs dfs -ls -R /project/distrib_db) shows five JSONL files under articles, reads, and users paths with sizes around 1–1.5 MB. 

- The HDFS overview page confirms: 

   - Safemode is off. 

   - 1 Live DataNode. 

   - 5 blocks in the filesystem. 

   - No dead nodes. 

- The file explorer UI shows the directory structure, and clicking into each folder lists the exported JSONL files. 

These results confirm that the MongoDB → HDFS pipeline works end-to-end, even under the constraints of running on Apple Silicon. 

## **6.5 Development challenges and resolutions** 

Development highlighted several non-trivial technical issues at the data and infrastructure layers: 

## **MongoDB4 integration and routing correctness.** 

Adding the expansion node (MongoDB4) required changes to the routing and monitoring logic so that the system could recognize a fourth node without breaking existing assumptions about a three-node topology. Initially, the application either ignored MongoDB4 or treated it as if it were part of the primary replica set, which risked sending live queries to a node intended only as a migration target. This was solved by extending monitor_snapshot() and run_queries_data() to include DB4 explicitly, while keeping it out of routing paths for OLTP queries and migration-sensitive operations. The result is a clearer separation between operational nodes (DB1–DB3) and the expansion node (DB4), and more accurate node-status reporting. 

## **Consistency and correctness of Redis-backed reads.** 

Introducing Redis caching surfaced several consistency concerns. Early versions cached entire query result sets without carefully defining invalidation rules, which could have served stale data after write operations (e.g., new reads affecting rankings). The solution was to narrow the cache footprint to specific read-mostly objects (article metadata and popular ranking snapshots) and to introduce a cache_clear() hook that is invoked after write operations such as insert_read. This design keeps cache entries small, invalidation simple, and ensures that derived data (like Popular-Rank) does not diverge from the underlying MongoDB state for long. 

## **HDFS connectivity and write semantics in a containerized environment.** 

Getting the MongoDB → HDFS export pipeline working reliably on macOS/ARM required addressing multiple deep technical issues. 

The first was binary compatibility: the initial Hadoop images were amd64-only, so an alternative image had to be selected that would run under Apple Silicon. 

The second was HDFS permissions and safe mode: attempts to write to /project/distrib_db failed due to NameNode safe mode and insufficient permissions for the configured user. This was resolved by explicitly waiting for safe mode to end, creating the target directory, and adjusting permissions/ownership. 

The third was WebHDFS redirection and hostname resolution: the HDFS client receives redirects to internal hostnames such as datanode:9864 which are not directly resolvable from the host. This required adding host mappings and, ultimately, patching the client’s HTTP request handling to rewrite those hostnames to addresses reachable from the development environment. 

These challenges led to a more robust design: clearer separation of roles between MongoDB nodes, stricter control over what is cached and when it is invalidated, and a defensive HDFS integration that behaves correctly even under non-standard local deployment conditions. 

## **7. Conclusion** 

This project implemented a distributed article management system that satisfies and extends the course requirements for a DDBMS project. Through careful fragmentation of users, articles, reads, Be-Reads, and popularity rankings, the system distributes data across four MongoDB nodes while preserving logical consistency. A hot standby node provides resilience, Redis caching accelerates repeated queries, and an HDFS export pipeline enables archival and offline analytics. 

The Flask-based monitoring and query pages served both as a debugging tool and as a pedagogical artifact, making the distributed behavior visible and understandable. Iterative debugging and refactoring—especially around failover routing, Redis status display, and HDFS connectivity—were essential in reaching a robust implementation. 

Overall, the project demonstrates how classical DDBMS concepts (fragmentation, replication, failover) can be combined with modern technologies (Redis, Docker, HDFS) to form a realistic miniature of an industrial data center for article content. 

## **8. Future Work** 

Several directions could further strengthen the system: 

1. **Stronger consistency checks and repairs.** 

Current replica checks focus on counts and simple invariants. Future work could include content-level checksum comparisons and automatic repair scripts to reconcile mismatched replicas. 

## 2. **Automated failover and recovery.** 

At present, failover is logical at the application layer. Integrating MongoDB replica sets and using their built-in election mechanisms would more closely mirror production deployments. 

## 3. **More granular caching strategy.** 

Expanding caching beyond article metadata and rankings—for example, caching query results per user or per query pattern—could offer additional performance gains, but would require more complex invalidation policies. 

## 4. **Richer analytics on HDFS.** 

Currently, HDFS is used as a dump of JSONL files. Implementing Spark or MapReduce jobs over the exported data would enable advanced analyses such as cohort retention, per-category engagement, or temporal trends. 

## 5. **Security and multi-tenant support.** 

Adding authentication, access control, and perhaps per-tenant fragmentation would make the system more directly applicable to real-world multi-tenant SaaS scenarios. 

## 6. **Deployment on cloud infrastructure.** 

Running the same architecture on a cloud provider (e.g., MongoDB Atlas, managed Redis, cloud storage instead of HDFS) would bridge the gap between the academic environment and production deployments. 

## **9. References** 

1. MongoDB, “What Is A Distributed Database?”, MongoDB Resources, 2025. 

2. GeeksforGeeks, “Distributed Database System”, June 2018. 

3. Fivetran, “The ultimate guide to using distributed databases”, Dec. 2022. 

4. Chapter 15, “Distributed Database Systems”, Database Systems notes, University of Cape Town. 

5. Hazelcast, “Lambda Architecture Overview: What Are the Benefits?”, 2025. 

6. Redis, “An Introduction to Velocity-Based Data Architectures”, Redis Labs Blog, 2023. 

7. Talk Python Training, “Eve: Building RESTful APIs with MongoDB and Flask”. 

8. AppSignal, “How to Use MongoDB in Python Flask”, 2025. 

9. Apache HaDoop “HDFS Architecture”, 2023. 

