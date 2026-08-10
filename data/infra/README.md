# Infrastructure

The storage your pipeline lands raw files in, described as code. Deploying it
is one command, and running that command twice does nothing the second time,
which is the property that makes infrastructure as code worth the effort.

## What it creates

| Resource | Why |
|---|---|
| ADLS Gen2 storage account | Holds raw files exactly as the source returned them |
| Container `raw` | Where your ingestion job writes |
| Lifecycle rule | Deletes raw files older than 90 days, so storage does not grow forever |
| Role assignment | Lets your Container Apps job write, once you pass its identity |

Account keys are switched off. Everyone authenticates as themselves: your own
Azure login while you develop, the job's managed identity once it runs in
Azure. There is no key to put in `.env` and none to leak.

## Deploy it

```bash
cd data/infra
az deployment group create \
  --resource-group <your-rg> \
  --template-file main.bicep \
  --parameters teamName=teama
```

Copy `abfssPath` from the output into your notes and `storageName` into
`STORAGE_ACCOUNT` in `.env`.

Your Container Apps job does not exist yet on the first deploy, so leave
`ingestPrincipalId` empty. Once the job is created, deploy again with its
identity so it can write:

```bash
az deployment group create \
  --resource-group <your-rg> \
  --template-file main.bicep \
  --parameters teamName=teama ingestPrincipalId=<the job's principal id>
```

## How Databricks reads these files

Your teachers point a volume in your catalog at this container, so
`/Volumes/<your catalog>/landing/raw/` and the container are the same files
seen from two sides. Your dbt models read the volume path and never mention the
storage account, which means you can move the storage later without touching a
model.

Give a teacher the `storageId` output when your storage account exists. Nothing
in dbt works until that link is made.

## Making it yours

Two decisions are yours, and both are marked in `main.bicep`:

- **`retentionDays`.** Ninety days is a guess. Raw files are cheap but not
  free, and re-reading a year of history is only possible if you kept it.
- **The container layout.** `blob_name` in `src/storage.py` decides how files
  are named inside the container, and dbt reads whatever you choose.
