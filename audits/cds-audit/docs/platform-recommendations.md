# Fixing problems at the platform level

Some guideline misses come from how the upload flow behaves, not from individual publishers. These
recommendations come from reading `DataSpaceBackend` while building the auditor. Fixing them once in the
product prevents the same issue on every future dataset.

**1. The license silently defaults to CC BY 4.0.**
`Dataset.license` defaults to `CC_BY_4_0_ATTRIBUTION`. A publisher who never opens the field ships
government-sourced data under the wrong licence, which breaks guideline 1.9. Recommendations:
- Make the licence an explicit choice with no default.
- Suggest GODL when the source-website field is a `.gov.in`, `.nic.in` or `data.gov.in` address.

The audit reports these datasets as "platform default — likely never set".

**2. Column descriptions look filled in when they aren't.**
Indexing writes `Description of column {name}` into every schema row. A reviewer scanning the schema sees
text everywhere, but no units or meaning have been documented (guideline 2.5). Recommendations:
- Leave the field empty.
- Show "Add a description" prompts, especially for numeric columns.

**3. Downloads by tools count as public downloads.**
`/api/download/resource/{id}` increments `download_count` for every request, including this auditor's deep
mode, CI jobs and crawlers. Recommendations:
- Skip counting for known automation User-Agents, or
- Add a non-counting internal download route for audits.

**4. Most section 2 checks could run at upload time.**
Several checks can be computed from the dataframe the indexer already loads: UTF-8 validity, column naming,
ISO dates, formatted numbers, `-999` sentinels, duplicate rows, Excel-without-CSV, and file naming. Running
them during indexing lets the upload screen warn the publisher before the dataset is published. That is far
cheaper than chasing publishers afterwards. The check functions in `src/cds_audit/checks/data.py` take plain
header and row lists, so they can be lifted into the backend largely as-is.

**5. Prompt for the metadata the guidelines require.**
Date of creation and source website are optional metadata items today, so they are easy to leave blank.
Recommendations:
- Make both required for published datasets.
- Validate the date as `YYYY-MM-DD` and the URL as `https://` on save.
