# Real arrival traces (experiment R1)

Derived from the **Huawei Private 2023** serverless trace (requests per minute), released by Huawei's Systems Infrastructure Research lab under **CC BY 4.0**: https://github.com/sir-lab/data-release

Source paper: A. Joosen et al., "How does it function? Characterizing long-term trends in production serverless workloads," in *Proc. ACM SoCC*, 2023, doi: 10.1145/3620678.3624783.

Changes: days 28–55 of the release only; functions 150, 72, 60, 183, 42 only; each series thinned binomially to a mean of 600 requests/min (`make_csvs.py`, seeds 20261031 + function id). `pick.py` lists the selection statistics; `traces_meta.json` records the thinning and SHA-256 of each file. To rebuild, download `requests_minute.zip` from the release, extract to `requests_minute/`, and run `pick.py` then `make_csvs.py` (paths inside the scripts point to the extraction directory).
