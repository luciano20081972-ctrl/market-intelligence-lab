# High-density data-source audit

Audit date: 2026-08-07. Storage ranges are planning estimates for normalized metadata plus selectively retained payloads, not vendor guarantees. “Free” excludes compute, storage, egress, engineering, and possible commercial market-data rights. Terms, redistribution, attribution, and rate limits must be rechecked before production. Every adapter must support ordinary tests from small licensed/synthetic fixtures without live credentials.

## Priority order for beta

1. SEC EDGAR submissions and filing archives
2. SEC Company Facts/XBRL bulk
3. FRED/ALFRED vintages
4. BLS
5. BEA
6. EIA
7. Census economic/ACS datasets
8. Federal Register and Congress.gov
9. NOAA/NASA POWER routed weather/climate
10. GDELT routed event metadata

This ranking favors broad economic coverage, authoritative provenance, point-in-time value, and low acquisition cost. Sector-specific sources such as NASS, SSURGO, Landsat, and Copernicus can outrank general feeds for an agriculture, mining, energy, logistics, or physical-asset company.

## Corporate, macro, energy, government, events

| Source | Coverage, history, refresh | Access, auth, limits, terms | Point-in-time and revisions | Storage and incremental ingestion | Sectors / beta / cost / fixtures |
|---|---|---|---|---|---|
| SEC EDGAR Submissions/Archives | US public-filer histories and documents; decades; submissions near-real-time | JSON API + nightly `submissions.zip` + archive; no key, declared user agent/fair-access policy; public filings, verify SEC policy | Acceptance/dissemination timestamp is authoritative; amendments append and filing metadata can update | 20-100 GB metadata/text for a selected universe; nightly bulk diff plus recent filing index | All public companies; P0; low; yes |
| SEC Company Facts/XBRL | Standard/custom facts across filings; XBRL era; under-minute typical API update | JSON endpoints + nightly `companyfacts.zip`; no key; same fair-access policy | Report period is not availability; preserve accession, filed time, form, frame, units, dimensions, amended versions | 10-100 GB normalized selected universe; nightly bulk checksum and accession/version upsert-as-append | All issuers/fundamentals; P0; low; yes |
| Existing market providers | Stooq delayed/fixed CSV, Twelve Data credentialed JSON, synthetic tests; provider-specific history/refresh | Existing fixed-host adapters; Twelve Data key/tier limits and market-data terms; redistribution may be restricted | Vendor timestamps often lack authoritative first-publication/adjustment semantics; store provider class and correction versions | 10-500 GB daily/minute selected universe; symbol/date watermarks and reconciliation | All securities; P0 foundation; free-to-commercial depending tier; yes |
| FRED/ALFRED | Broad US/global economic series, long histories; release-dependent | REST v1/v2; API key; documented pagination/limits; St. Louis Fed terms | ALFRED real-time periods/vintage dates explicitly preserve what was known and later revised | 5-50 GB for selected series/all vintages; release/series watermarks and vintage-date polling | All sectors/macro; P0; low; yes |
| BLS Public Data API | Labor, inflation, wages, productivity; program-dependent history; scheduled releases | REST v2 JSON/XLSX; registration key raises limits (registered requests can include up to 50 series); BLS terms | Values have preliminary/revised footnotes; publication calendar must be captured separately | 2-20 GB selected series; release calendar plus last-N-period refresh and revision append | Labor-intensive/consumer/all; P0; low; yes |
| BEA API | GDP, industry, regional, international and national accounts; decades; scheduled | REST at `apps.bea.gov/api/data`; free registered UserID; discoverable datasets/parameters; BEA terms | Revised vintages/releases require captured publication and retrieval snapshots; API is current-view oriented | 5-30 GB selected tables/vintages; dataset metadata diff and release-window refresh | Macro, industries, regions; P0/P1; low; yes |
| Census APIs | ACS, Economic Census, business patterns, trade, population, geography; vintage-dependent | REST discovery/data APIs; key for sustained use; dataset/query limits; Census terms | Vintage/reference year differs from release availability; revisions/estimate margins retained | 20-200 GB selected tables/geographies; dataset-vintage manifests and release refresh | Consumer, housing, regional, retail, labor; P1; low; yes |
| EIA Open Data | Electricity, petroleum, natural gas, coal, renewables, prices/capacity; long series; daily-weekly-monthly | REST v2, free key, pagination/rate policy; US government data terms | Preserve period, updated timestamp, release schedule, provisional/revised status | 10-100 GB targeted series; route discovery, frequency watermarks, refresh recent periods | Energy, industrials, transport, utilities; P0/P1; low; yes |
| Congress.gov | Bills, laws, actions, sponsors, subjects, texts, votes/records; Congress-dependent; frequent | OpenAPI REST, `api.data.gov` key, quotas; official public legislative data | Action date, API update, text version/publication and law effective date are distinct | 5-50 GB metadata/selected text; `updateDate` cursor/pagination and version hashes | Regulated industries/policy; P1; low; yes |
| Federal Register | Rules, proposed rules, notices, executive documents, agencies; modern digital history; daily | Public REST API, typically no key; documented courtesy limits/terms | Publication date, effective date, comment deadlines, correction documents differ | 5-30 GB metadata/selected text; publication-date cursor and document-number versions | Regulated sectors; P1; low; yes |
| GDELT 2.0 Events/GKG | Global multilingual events/news-derived entities/themes; 2015+ for v2; 15-minute updates | Bulk 15-minute files, BigQuery/other access; no key for bulk; source/content rights remain with publishers | Capture/update time available; underlying article publication quality varies; backfills/corrections and duplicate origins require caution | Targeted 0.2-2 TB/year versus huge full corpus; process file manifests, retain filtered rows and source URLs | Geopolitics, supply chains, global firms; P1 routed; medium; yes |

Authoritative references: [SEC APIs and nightly bulk files](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [FRED API](https://fred.stlouisfed.org/docs/api/fred/), [ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html), [BLS API v2](https://www.bls.gov/developers/api_signature_v2.htm), [BEA API guide](https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf), [Census API guide](https://www.census.gov/data/developers/guidance/api-user-guide.html), [EIA API](https://www.eia.gov/opendata/documentation.php), [Congress.gov OpenAPI](https://api.congress.gov/), [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1), [GDELT data](https://www.gdeltproject.org/data.html).

## Agriculture, weather, geospatial, scientific, web-scale

| Source | Coverage, history, refresh | Access, auth, limits, terms | Point-in-time and revisions | Storage and incremental ingestion | Sectors / beta / cost / fixtures |
|---|---|---|---|---|---|
| USDA NASS Quick Stats | Crops, livestock, prices, acreage, production, location/time; long survey histories; release-driven | Quick Stats API + downloads; free key; row/request constraints; USDA terms | Publication/release and reference period differ; estimates revise | 5-50 GB selected commodities/geos; release calendar + updated series partitions | Agriculture, food, fertilizer, machinery; P1 for ag beta; low; yes |
| USDA ERS | Farm economics, trade, food, productivity and ARMS; dataset-specific; annual/periodic | REST/GraphQL for select products + bulk; `api.data.gov` key for APIs; terms per product | Explicit update/revision histories on some products; preserve dataset edition | 5-100 GB depending ARMS/bulk selection; edition manifests and updated endpoints | Agriculture/consumer/trade; P2; low; yes |
| USDA NRCS SSURGO | US soil polygons/properties/interpretations; century of survey work, annual refresh | Web Soil Survey/Soil Data Access + county/all-US downloads; no ordinary API key; public-data terms | Annual official refresh; survey vintage and incomplete areas explicit | Full all-US GeoPackage about 28 GB cited by NRCS, derived indexes extra; annual snapshot/diff by survey area | Agriculture, land, construction, insurance; P1 routed; low-medium; yes |
| NOAA NCEI | Global weather/climate/ocean/geophysical archives; station history varies; near-real-time to annual | CDO v2/search/data/OGC/OPeNDAP/bulk; token for CDO (5 req/s, 10k/day documented); NOAA terms | Operational, QC, normals and reanalysis versions differ; station metadata changes | 50 GB to multi-TB; retain selected stations/grids, dataset manifests and time partitions | Airlines, energy, agriculture, insurance, logistics; P1 routed; medium; yes |
| NASA POWER | Global analysis-ready solar/meteorological hourly/daily/monthly, 1981-near-real-time for daily | REST microservices, JSON/CSV/NetCDF; no key; documented 429/parameter/spatial limits | Improved climate-quality products replace meteorology about 2-3 months later | 5-100 GB for routed points/regions; re-fetch recent correction window and store product version | Energy, agriculture, infrastructure; P1 routed; low; yes |
| ECMWF Open Data | Subset of real-time global forecasts; forecast cycles and horizons | HTTP/S3/Azure/Google/Open Data clients; no key for open subset; CC-BY-4.0 noted by ECMWF, verify product license | Model run/step/valid time distinct; forecasts expire/reprocess; archive availability limited versus live feed | 0.1-5 TB/year if broadly retained; ingest only routed variables/AOIs per run | Airlines, energy, agriculture, shipping; P2; medium-high; yes |
| USGS event/physical APIs | Earthquakes, water, minerals, land/elevation and other dataset-specific products; varied depth/refresh | Multiple REST/bulk services; mostly no key; terms per product | Event/review/revision statuses and product versions vary | 5-200 GB targeted; source-specific update cursors/manifests | Mining, utilities, insurance, infrastructure; P2 routed; low-medium; yes |
| Landsat Collection 2 | Global land imagery since 1972; revisit/product dependent | EarthExplorer, M2M API, AWS cloud, bulk metadata; accounts for some services; no-cost data | Acquisition, processing/publication, collection/reprocessing and cloud mask/QC distinct | Metadata tens of GB; imagery becomes multi-TB quickly—store AOI-derived artifacts/references | Agriculture, mining, industrial facilities, forestry, water; P2 routed; medium-high; yes |
| Sentinel/Copernicus Data Space | Sentinel-1/2/3 etc global radar/optical/ocean/atmosphere; mission-dependent; frequent | STAC, OData, S3 and Sentinel Hub APIs; account/token depending service; EU data terms/license | Sensing, publication, processing baseline and reprocessing versions distinct | Metadata tens/hundreds GB; selected imagery multi-TB—STAC references + routed AOIs | Physical assets, shipping, agriculture, mining, climate; P2 routed; medium-high; yes |
| OpenAlex | Scholarly works, authors, institutions, sources, topics/citations; broad historical graph; frequent snapshots/API updates | REST API + free snapshot; key/polite-pool policies as current docs specify; CC0 data | `publication_date` differs from indexed/updated time; records and concepts/topics revise | Full snapshot hundreds of GB compressed/order-of-TB loaded; beta stores topic/organization subsets | Technology, pharma, R&D; P2; medium; yes |
| Crossref | DOI scholarly metadata, funding, licenses, updates/retractions; broad history; continuous deposits | Public REST + annual public file; no signup, polite `mailto`; almost all metadata reusable, abstracts may be copyrighted | Created/deposited/indexed/published/update relations are distinct; member records redeposit | Full annual file hundreds of GB; beta selected works 10-100 GB; cursor by update/index date | Technology, pharma, R&D; P2; low-medium; yes |
| arXiv metadata | Preprints and versions across scientific fields; 1991+; daily | Atom API/OAI-PMH/Kaggle or S3 bulk programs as applicable; API rate courtesy; arXiv terms | Submission/version announcement time matters; journal publication is separate | Metadata/sources/PDFs range from GB to multi-TB; OAI datestamp and version incremental | AI, semiconductors, biotech, energy research; P2; medium; yes |
| Common Crawl | Multi-billion-page web snapshots; recurring crawls; WARC/WAT/WET + indexes | Free HTTP/S3 Open Data; CDXJ and Parquet URL index; no account for HTTP; respect source copyrights/robots/opt-outs and legal policy | WARC capture time is known but page publication can be unknown; crawls are snapshots, deletions/corrections complex | Hundreds of TB per crawl; never mirror for beta—query index, range-fetch selected records, retain hashes/extracts under policy | Discovery across sectors; P3 exceptional route; medium-high; yes |

Authoritative references: [NASS developers](https://www.nass.usda.gov/developer/), [ERS APIs](https://www.ers.usda.gov/developer), [NRCS SSURGO](https://www.nrcs.usda.gov/resources/data-and-reports/ssurgo-portal), [NOAA NCEI services](https://www.ncei.noaa.gov/cdo-web/webservices), [NASA POWER API](https://power.larc.nasa.gov/docs/services/api/), [ECMWF open data](https://www.ecmwf.int/en/forecasts/datasets/open-data), [USGS Landsat access](https://www.usgs.gov/landsat-missions/landsat-data-access), [Copernicus STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), [OpenAlex API](https://docs.openalex.org/how-to-use-the-api), [Crossref REST](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [arXiv API](https://info.arxiv.org/help/api/), [Common Crawl](https://commoncrawl.org/get-started).

## Additional consolidated candidates

- **USASpending.gov:** contracts/grants and recipient/agencies; high value for government-dependent firms. P2.
- **EPA Envirofacts/ECHO and eGRID:** facilities, enforcement, emissions, grid characteristics. P2 for industrial/utilities.
- **BTS/FAA operational datasets:** transport, airport and airline metrics. P2 for airlines/logistics.
- **UN Comtrade / World Bank / IMF open APIs:** trade and global macro; terms/rate/vintage behavior require separate audit. P2.
- **USPTO PatentsView / bulk patent data:** innovation, assignees, citations; identity resolution is substantial. P2 for technology/pharma.

## Largest gaps

1. Authoritative supply-chain/customer relationships and contract economics.
2. Facility-level capacity, utilization, energy intensity, and timely shutdown/expansion data.
3. Licensed high-quality market fundamentals/estimates, corporate actions, intraday data, and point-in-time symbology.
4. Private-company, international filing, ownership, and subsidiary coverage.
5. Shipping/port/container, air traffic, web/app transaction, job-posting, and card-spend data with commercial rights.
6. Reliable first-publication timestamps for news and web content.
7. Entity resolution across facilities, subsidiaries, research institutions, patents, agencies, and geospatial assets.
8. Ground truth for causal driver relationships and sufficiently many independent market regimes.

## Ingestion policy

Use bulk snapshots for bootstrap, API/change feeds for deltas, immutable source manifests and hashes, small recent-period correction windows, and dataset-specific temporal policies. Land large payloads in object storage, normalize only routed fields, and keep raw-to-derived lineage. Live calls are bounded rehearsals; CI and ordinary tests use fixtures.
